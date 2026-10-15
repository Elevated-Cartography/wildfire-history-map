"""Turn the fetched raw layers into a pmtiles file and site metadata."""

import hashlib
import json
import logging
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Dict, List, Set, Tuple

import pyproj
from pint import UnitRegistry
from shapely.geometry import shape
from shapely.ops import transform
from tqdm import tqdm

from .boundaries import Boundaries
from .fetch import read_meta
from .reason import NIFCRulesEngine, ReasonCode
from .source import Config, Lookup, Source
from .tiles import Fire, build_tiles, install_tiles

log = logging.getLogger(__name__)

# Properties every output feature has. Missing strings are "", missing
# numbers are left out (tippecanoe drops nulls).
STRING_PROPS = ["agency", "fire_name", "comments", "alarm_date", "cont_date"]
DATE_PROPS = ["alarm_date", "cont_date"]

# Burn times longer than this are almost certainly bad dates
MAX_DURATION_DAYS = 730

# Properties included in fires.json, the full list of fires the site's table
# shows (the tiles only have what's on screen, simplified at low zooms)
FIRE_LIST_PROPS = [
    "id", "key", "year", "fire_name", "cause", "size", "agency", "source", "kind",
    "states", "countries", "duration_days", "month", "alarm_date", "cont_date",
    "comments",
]
# Bounding boxes are rounded outwards to this many decimal places (~100m)
BBOX_DECIMALS = 3

epsg_4326 = pyproj.CRS.from_epsg(4326)


def get_utm_zone(lon, lat):
    # Determine the UTM zone based on the longitude
    zone = (int(lon) + 180) // 6 + 1

    # Construct the EPSG code for the UTM zone
    epsg_code = 32600 + zone if lat >= 0 else 32700 + zone
    return epsg_code


def normalize_irwinid(irwinid):
    """IRWIN IDs show up as {GUID}, GUID, upper or lower case depending on source."""
    if not irwinid:
        return None
    return irwinid.strip().strip("{}").upper() or None


def to_iso_date(val):
    """ArcGIS returns dates as epoch milliseconds."""
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000, timezone.utc).isoformat()
    return str(val)


def to_year(val):
    try:
        year = int(val)
    except (TypeError, ValueError):
        return None
    # Sources use things like 0 and 9999 for "unknown"
    return year if 100 < year < 9999 else None


def duration_days(alarm_date, cont_date):
    """Days from discovery to containment, from two ISO dates, if both are known
    and plausible."""
    if not alarm_date or not cont_date:
        return None
    try:
        days = (
            datetime.fromisoformat(cont_date) - datetime.fromisoformat(alarm_date)
        ).total_seconds() / 86400
    except ValueError:
        return None
    return round(days, 2) if 0 <= days <= MAX_DURATION_DAYS else None


def to_month(iso_date):
    try:
        return datetime.fromisoformat(iso_date).month
    except (TypeError, ValueError):
        return None


def delimited(values):
    """Pack a list into one string for filtering on the map: "|US-CA|US-NV|".

    Vector tiles can't hold lists, and the delimiters at both ends mean a
    filter can look for "|US-CA|" without matching codes that merely contain it.
    """
    return f"|{'|'.join(values)}|" if values else None


def rounded_bbox(bounds):
    """Round a (minx, miny, maxx, maxy) box outwards, so it still contains the fire."""
    scale = 10**BBOX_DECIMALS
    minx, miny, maxx, maxy = bounds
    return [
        math.floor(minx * scale) / scale,
        math.floor(miny * scale) / scale,
        math.ceil(maxx * scale) / scale,
        math.ceil(maxy * scale) / scale,
    ]


def fire_key_basis(source_name, irwinid, year, name, centroid):
    """What a fire's link key is made from. IDs from the build (`id`) are just
    processing order and change whenever the data does, so links use this.

    The IRWIN ID is the national incident ID, so it survives a perimeter
    growing or moving between sources. Fires without one fall back to their
    source, year, name and centroid to ~1km.
    """
    if irwinid:
        return f"irwin:{irwinid}"
    name = (name or "").strip().lower()
    return f"{source_name}|{year}|{name}|{centroid.x:.2f}|{centroid.y:.2f}"


def write_fire_list(fires, path):
    """Write fires.json: one array per property (column-oriented, which
    compresses far better than an array of objects), plus `bbox`."""
    columns = {name: [fire[0].get(name) for fire in fires] for name in FIRE_LIST_PROPS}
    # Square meters to the nearest one is plenty
    columns["size"] = [round(v) if v is not None else None for v in columns["size"]]
    columns["bbox"] = [rounded_bbox(fire[1]) for fire in fires]
    with open(path, "w") as f:
        json.dump({"count": len(fires), "columns": columns}, f, separators=(",", ":"))


def field_value(props, field):
    """A mapped field's value: `field` is a field name, or a list of them to
    take the first non-empty value from."""
    for name in field if isinstance(field, list) else [field]:
        value = props.get(name)
        if value not in (None, "", " "):
            return value
    return None


def read_geojsonl(path):
    with open(path) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


@dataclass
class Metadata:
    years: List[int]
    min_year: int
    max_year: int
    generated_at: str
    sources: List[dict] = field(default_factory=list)
    # [{code, name, count}] for the filters, most fires first
    countries: List[dict] = field(default_factory=list)
    # [{code, name, country, count}]
    regions: List[dict] = field(default_factory=list)
    # The tiles files, [{url, bounds, fires, bytes}] (see tiles.py)
    tiles: List[dict] = field(default_factory=list)
    # The fires.json file (named with the build version, like the tiles)
    fire_list: str = "fires.json"


class SourceProcessor:
    def __init__(self, config: Config, data_dir: Path):
        self.config = config
        self.data_dir = data_dir
        self.processed_dir = data_dir / "processed"
        self.seen_irwinids: Set[str] = set()
        # (year, name) -> bounding boxes of fires we've kept with that key
        self.seen_fires: Dict[Tuple[int, str], List[tuple]] = {}
        self.seen_years: Set[int] = set()
        self.ureg = UnitRegistry()
        self.transformers_cache = {}
        self.nifc_rules_engine = NIFCRulesEngine()
        self.lookups: Dict[str, Dict[str, tuple]] = {}
        self.boundaries = Boundaries(config.boundaries_path(data_dir))
        self.region_counts = Counter()
        # (properties, bounds, bytes of GeoJSON) of every fire kept, for
        # fires.json and splitting the tiles
        self.fire_list = []
        self.seen_keys: Set[str] = set()
        self.country_counts = Counter()
        # Feature IDs start at 1: tippecanoe can't use 0 as an ID ("Can't
        # represent too-large feature ID 0"), and MapLibre needs IDs to
        # highlight features
        self.cur_id = 1
        self.stats = {}

    def process(self):
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        for lookup in self.config.lookups.values():
            self._load_lookup(lookup)
        processed = []
        for source in self.config.sources:
            processed.append(self._process_source(source))
        years = sorted(self.seen_years)
        meta = Metadata(
            years=years,
            min_year=years[0],
            max_year=years[-1],
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            sources=[self._source_meta(s) for s in self.config.sources],
            countries=[
                {"code": country[0], "name": country[1], "count": count}
                for country, count in self.country_counts.most_common()
            ],
            regions=[
                {"code": r.code, "name": r.name, "country": r.country_code, "count": count}
                for r, count in self.region_counts.most_common()
            ],
        )
        return processed, meta

    def _source_meta(self, source: Source):
        fetch_meta = read_meta(source.raw_path(self.data_dir)) or {}
        last_edit = fetch_meta.get("version", {}).get("last_edit")
        return {
            "name": source.name,
            "title": source.title,
            "homepage": source.homepage,
            "fetched_at": fetch_meta.get("fetched_at"),
            "last_edit": to_iso_date(last_edit) if last_edit else None,
            **self.stats.get(source.name, {}),
        }

    def _load_lookup(self, lookup: Lookup):
        table = {}
        for feature in tqdm(
            read_geojsonl(lookup.raw_path(self.data_dir)), desc=f"Loading {lookup.name}"
        ):
            props = feature["properties"]
            key = normalize_irwinid(props.get(lookup.key_field))
            if key:
                table[key] = tuple(props.get(f) for f in lookup.fields)
        self.lookups[lookup.name] = table

    def _unique_key(self, basis):
        """12 hex characters is short enough for a URL, and collisions are
        unlikely at this scale. The rare ones (two unnamed fires in the same
        place and year) get a suffix, which is stable as long as the source
        data keeps its order."""
        n = 0
        while True:
            text = basis if n == 0 else f"{basis}#{n}"
            key = hashlib.sha1(text.encode()).hexdigest()[:12]
            if key not in self.seen_keys:
                self.seen_keys.add(key)
                return key
            n += 1

    def _next_id(self):
        id = self.cur_id
        self.cur_id += 1
        return id

    def _ensure_multipolygon(self, geometry):
        if geometry["type"] == "MultiPolygon":
            return geometry
        elif geometry["type"] == "Polygon":
            # Wrap it in an extra list to convert to multipolygon
            return {"type": "MultiPolygon", "coordinates": [geometry["coordinates"]]}
        return None

    def _get_transformer(self, utm_zone):
        if utm_zone not in self.transformers_cache:
            self.transformers_cache[utm_zone] = pyproj.Transformer.from_crs(
                epsg_4326, utm_zone, always_xy=True
            )
        return self.transformers_cache[utm_zone]

    def _fallback_size_compute(self, feature_shape):
        centroid = feature_shape.centroid
        utm_zone = get_utm_zone(centroid.x, centroid.y)
        transformer = self._get_transformer(utm_zone)
        transformed_shape = transform(transformer.transform, feature_shape)
        return transformed_shape.area

    def _retrieve_size(self, props, feature_shape, source: Source):
        """Fire size in square meters."""
        try:
            size = float(props[source.size_field])
        except (KeyError, TypeError, ValueError):
            return self._fallback_size_compute(feature_shape)
        unit = getattr(self.ureg, source.size_unit)
        return (size * unit).to(self.ureg.meter**2).magnitude

    def _resolve_cause(self, source: Source, props, irwinid, direct):
        """Use the source's own cause code if it has a real one, otherwise try
        to work one out from NIFC-style cause fields."""
        if source.cause.values and direct is not None:
            # e.g. NBAC's "Natural" -> Lightning
            direct = source.cause.values.get(str(direct))
        if direct not in (None, "", ReasonCode.UNNOWN_UNIDENTIFIED.num):
            return direct
        cause_fields = None
        if source.cause.fields:
            cause_fields = tuple(props.get(f) for f in source.cause.fields)
        elif source.cause.lookup and irwinid:
            cause_fields = self.lookups[source.cause.lookup].get(irwinid)
        if cause_fields:
            reason = self.nifc_rules_engine.match(*cause_fields)
            if reason and (direct in (None, "") or reason != ReasonCode.UNNOWN_UNIDENTIFIED):
                return reason.num
        return direct if direct != "" else None

    def _is_duplicate_fire(self, year, name, bounds):
        """Same year, same name and overlapping extents means the same fire.

        Unnamed fires never match. Requiring overlap stops fires that just
        share a common name ("Lone Mountain") in the same year from colliding.
        """
        if not name:
            return False
        key = (year, name.strip().lower())
        minx, miny, maxx, maxy = bounds
        for ominx, ominy, omaxx, omaxy in self.seen_fires.get(key, []):
            if minx <= omaxx and ominx <= maxx and miny <= omaxy and ominy <= maxy:
                return True
        self.seen_fires.setdefault(key, []).append(bounds)
        return False

    def _process_source(self, source: Source):
        stats = {"kept": 0, "no_geometry": 0, "duplicate": 0, "bad_geometry": 0}
        out_path = self.processed_dir / f"{source.name}.geojsonl"
        with open(out_path, "w") as out:
            for feature in tqdm(
                read_geojsonl(source.raw_path(self.data_dir)),
                desc=f"Processing {source.name}",
            ):
                in_props = feature["properties"]
                geometry = feature.get("geometry")
                if not geometry:
                    stats["no_geometry"] += 1
                    continue
                geometry = self._ensure_multipolygon(geometry)
                if geometry is None:
                    stats["bad_geometry"] += 1
                    continue

                # Clean up any features with duplicate irwinids
                irwinid = normalize_irwinid(in_props.get(source.irwinid_field))
                if irwinid in self.seen_irwinids:
                    stats["duplicate"] += 1
                    continue

                # Grab all the items from the field map
                props = {name: field_value(in_props, f) for name, f in source.fields.items()}
                for name in DATE_PROPS:
                    props[name] = to_iso_date(props.get(name))
                year = to_year(props.get("year"))
                if year is None and props.get("alarm_date"):
                    year = to_year(props["alarm_date"][:4])
                props["year"] = year
                props["cause"] = self._resolve_cause(
                    source, in_props, irwinid, props.get("cause")
                )

                feature_shape = shape(geometry)
                # A few records sit at 0,0 ("Null Island"): a missing location,
                # not a fire off the coast of Africa
                minx, miny, maxx, maxy = feature_shape.bounds
                if max(abs(minx), abs(miny), abs(maxx), abs(maxy)) < 1:
                    stats["bad_geometry"] += 1
                    continue
                if self._is_duplicate_fire(
                    year, props.get("fire_name"), feature_shape.bounds
                ):
                    stats["duplicate"] += 1
                    continue
                if irwinid:
                    self.seen_irwinids.add(irwinid)
                if year is not None:
                    self.seen_years.add(year)

                props["size"] = self._retrieve_size(in_props, feature_shape, source)
                props["source"] = source.name
                props["kind"] = (
                    "prescribed"
                    if source.prescribed.field
                    and in_props.get(source.prescribed.field) in source.prescribed.values
                    else "wildfire"
                )
                props["duration_days"] = duration_days(
                    props["alarm_date"], props["cont_date"]
                )
                props["month"] = to_month(props["alarm_date"])

                regions = self.boundaries.regions_for(feature_shape)
                countries = sorted({(r.country_code, r.country_name) for r in regions})
                props["states"] = delimited([r.code for r in regions])
                props["countries"] = delimited([code for code, _ in countries])
                self.region_counts.update(regions)
                self.country_counts.update(countries)

                props["id"] = self._next_id()
                props["key"] = self._unique_key(
                    fire_key_basis(
                        source.name,
                        irwinid,
                        year,
                        props.get("fire_name"),
                        feature_shape.centroid,
                    )
                )
                # Assign default values to any missing props
                for name in STRING_PROPS:
                    if props.get(name) is None:
                        props[name] = ""
                props = {k: v for k, v in props.items() if v is not None}

                # The link key is only needed in fires.json, not in every tile
                tile_props = {k: v for k, v in props.items() if k != "key"}
                out_feature = {"type": "Feature", "properties": tile_props, "geometry": geometry}
                line = json.dumps(out_feature, separators=(",", ":")) + "\n"
                out.write(line)
                self.fire_list.append((props, feature_shape.bounds, len(line.encode())))
                stats["kept"] += 1

        self.stats[source.name] = stats
        print(f"{source.name}: {stats}")
        return out_path


def find_tippecanoe(explicit=None):
    path = explicit or os.environ.get("TIPPECANOE") or which("tippecanoe")
    if not path:
        raise RuntimeError(
            "Couldn't find tippecanoe. Put it on your PATH, set $TIPPECANOE, "
            "or pass --tippecanoe."
        )
    return path


def build(config: Config, data_dir: Path, out_dir: Path, tippecanoe=None, max_tile_mb=100):
    tippecanoe_path = find_tippecanoe(tippecanoe)
    out_dir.mkdir(parents=True, exist_ok=True)

    sp = SourceProcessor(config, data_dir)
    processed_files, meta = sp.process()

    unmatched = sp.nifc_rules_engine.unmatched
    if unmatched:
        print(f"{len(unmatched)} cause combinations had no matching rule "
              "(run `surtr reason-test` to list them)")

    # Built in data/processed, not out_dir: that's Vite's public dir, and a
    # site build in the meantime would copy half-written files
    fires = [
        Fire(
            id=props["id"],
            x=(bounds[0] + bounds[2]) / 2,
            y=(bounds[1] + bounds[3]) / 2,
            weight=weight,
            bounds=bounds,
        )
        for props, bounds, weight in sp.fire_list
    ]
    built = build_tiles(
        tippecanoe_path,
        processed_files,
        fires,
        data_dir / "processed" / "tiles",
        max_bytes=int(max_tile_mb * 1_000_000),
    )
    # Output files are named with this (see install_tiles)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    meta.tiles = install_tiles(built, out_dir, version)

    for old in out_dir.glob("fires*.json"):
        old.unlink()
    meta.fire_list = f"fires-{version}.json"
    write_fire_list(sp.fire_list, out_dir / meta.fire_list)
    # Last, since it points at everything else
    with open(out_dir / "meta.json", "w") as f:
        json.dump(meta.__dict__, f, indent=2)

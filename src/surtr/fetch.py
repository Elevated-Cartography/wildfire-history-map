"""Download ArcGIS FeatureServer layers as newline-delimited GeoJSON.

Each layer is saved to data/raw/<name>.geojsonl alongside a <name>.meta.json
describing what was fetched. A layer is only re-downloaded when the server
says its data changed (or what we ask for changed), and the output file is
only replaced when a download finishes, so its mtime is a reliable signal for
make that there's new data.
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tqdm import tqdm

from .source import Layer

log = logging.getLogger(__name__)

CHUNK_SIZE = 250
WORKERS = 4
RETRIES = 4
TIMEOUT = httpx.Timeout(120.0, connect=30.0)


class FetchError(RuntimeError):
    pass


def _get_json(client, url, method="GET", **params):
    params["f"] = params.get("f", "json")
    for attempt in range(RETRIES):
        try:
            if method == "POST":
                r = client.post(url, data=params)
            else:
                r = client.get(url, params=params)
            r.raise_for_status()
            body = r.json()
            # ArcGIS reports most errors as a 200 with an error body
            if "error" in body:
                raise FetchError(f"{url}: {body['error']}")
            return body
        except (httpx.HTTPError, FetchError, json.JSONDecodeError) as e:
            if attempt == RETRIES - 1:
                raise
            wait = 2**attempt
            log.warning(f"Request failed ({e}), retrying in {wait}s")
            time.sleep(wait)


def layer_version(client, layer: Layer) -> dict:
    """What we'd fetch right now. If this matches the last fetch, skip it."""
    info = _get_json(client, layer.url)
    editing = info.get("editingInfo", {})
    return {
        "url": layer.url,
        "where": layer.where,
        "out_fields": layer.out_fields(),
        "return_geometry": layer.return_geometry,
        "last_edit": editing.get("dataLastEditDate") or editing.get("lastEditDate"),
        "max_record_count": info.get("maxRecordCount", 1000),
    }


def _meta_path(raw_path: Path) -> Path:
    return raw_path.with_suffix(".meta.json")


def read_meta(raw_path: Path):
    meta_path = _meta_path(raw_path)
    if raw_path.exists() and meta_path.exists():
        return json.loads(meta_path.read_text())
    return None


def _fetch_chunk(client, layer: Layer, ids):
    params = {
        "objectIds": ",".join(map(str, ids)),
        "outFields": ",".join(layer.out_fields()),
        "returnGeometry": str(layer.return_geometry).lower(),
        "outSR": 4326,
        "geometryPrecision": 6,
        "f": "geojson",
    }
    try:
        body = _get_json(client, f"{layer.url}/query", method="POST", **params)
        features = body.get("features", [])
        if len(features) < len(ids) and body.get("properties", {}).get(
            "exceededTransferLimit"
        ):
            raise FetchError("Transfer limit exceeded")
        return features
    except (httpx.HTTPError, FetchError):
        # Some fires have enormous polygons, so a chunk can be too big for the
        # server to return. Split it until it works or we're down to one.
        if len(ids) == 1:
            raise
        mid = len(ids) // 2
        log.warning(f"Splitting chunk of {len(ids)} for {layer.name}")
        return _fetch_chunk(client, layer, ids[:mid]) + _fetch_chunk(
            client, layer, ids[mid:]
        )


def fetch_layer(layer: Layer, data_dir: Path, force=False) -> bool:
    """Fetch a layer if it changed. Returns True if new data was written."""
    raw_path = layer.raw_path(data_dir)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        version = layer_version(client, layer)
        old_meta = read_meta(raw_path)
        if not force and old_meta and old_meta.get("version") == version:
            print(f"{layer.name}: up to date")
            return False

        ids = _get_json(
            client,
            f"{layer.url}/query",
            method="POST",
            where=layer.where,
            returnIdsOnly="true",
        )["objectIds"]
        ids = sorted(ids or [])
        chunk_size = min(CHUNK_SIZE, version["max_record_count"])
        chunks = [ids[i : i + chunk_size] for i in range(0, len(ids), chunk_size)]

        tmp_path = raw_path.with_suffix(".tmp")
        count = 0
        with open(tmp_path, "w") as out, ThreadPoolExecutor(WORKERS) as pool, tqdm(
            total=len(ids), desc=layer.name, unit="feat"
        ) as bar:
            # map() keeps chunk order, so output order is stable between runs
            for features in pool.map(
                lambda c: _fetch_chunk(client, layer, c), chunks
            ):
                for feature in features:
                    out.write(json.dumps(feature, separators=(",", ":")))
                    out.write("\n")
                count += len(features)
                bar.update(len(features))

    if count != len(ids):
        tmp_path.unlink()
        raise FetchError(f"{layer.name}: expected {len(ids)} features, got {count}")

    os.replace(tmp_path, raw_path)
    meta = {
        "name": layer.name,
        "title": layer.title,
        "homepage": layer.homepage,
        "count": count,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": version,
    }
    _meta_path(raw_path).write_text(json.dumps(meta, indent=2))
    print(f"{layer.name}: fetched {count} features")
    return True


def fetch_boundaries(url: str, path: Path, force=False) -> bool:
    """Download the state/province boundaries. They hardly ever change, so
    this only happens once unless forced."""
    if path.exists() and not force:
        print(f"boundaries: already downloaded ({path})")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with httpx.stream("GET", url, timeout=TIMEOUT, follow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp_path, "wb") as out:
            for chunk in r.iter_bytes():
                out.write(chunk)
    os.replace(tmp_path, path)
    print(f"boundaries: downloaded {path}")
    return True


GITHUB_API = "https://api.github.com"


def download_data(repo: str, tag: str, out_dir: Path, api: str = GITHUB_API):
    """Download the map data the "Update data" workflow published to the
    `tag` release of `repo` (see .github/workflows/data.yml), instead of
    building it. Uses $GITHUB_TOKEN or $GH_TOKEN if set, which a private repo
    needs."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # httpx drops the Authorization header when following the redirect to
    # GitHub's file storage, which is what that storage wants
    with httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        r = client.get(f"{api}/repos/{repo}/releases/tags/{tag}")
        if r.status_code == 404:
            raise FetchError(
                f"No {tag!r} release in {repo}. Run the 'Update data' workflow on GitHub "
                "to publish one, or build the data here with `make`."
                + ("" if token else " (If the repo is private, set GITHUB_TOKEN.)")
            )
        r.raise_for_status()
        assets = {asset["name"]: asset for asset in r.json()["assets"]}
        if "meta.json" not in assets:
            raise FetchError(f"The {tag!r} release in {repo} has no meta.json")

        def get(name):
            response = client.get(
                assets[name]["url"], headers={"Accept": "application/octet-stream"}
            )
            response.raise_for_status()
            return response

        meta_text = get("meta.json").text
        meta = json.loads(meta_text)
        names = [tile["url"] for tile in meta["tiles"]] + [meta.get("fire_list", "fires.json")]
        missing = [name for name in names if name not in assets]
        if missing:
            raise FetchError(f"The {tag!r} release is missing {', '.join(missing)}")

        out_dir.mkdir(parents=True, exist_ok=True)
        total = sum(assets[name]["size"] for name in names)
        with tqdm(total=total, unit="B", unit_scale=True, desc="Downloading map data") as bar:
            for name in names:
                path = out_dir / name
                # Names include the build version, so a file that's already
                # here at the right size is the same file (say, from a download
                # that got interrupted part way)
                if path.exists() and path.stat().st_size == assets[name]["size"]:
                    bar.update(assets[name]["size"])
                    continue
                tmp_path = path.with_suffix(".tmp")
                with client.stream(
                    "GET", assets[name]["url"], headers={"Accept": "application/octet-stream"}
                ) as response:
                    response.raise_for_status()
                    with open(tmp_path, "wb") as out:
                        for chunk in response.iter_bytes():
                            out.write(chunk)
                            bar.update(len(chunk))
                os.replace(tmp_path, path)

    # Drop files from other versions, then write meta.json last: it's what
    # points at the rest
    keep = set(names)
    for old in [*out_dir.glob("fire*.pmtiles"), *out_dir.glob("fires*.json")]:
        if old.name not in keep:
            old.unlink()
    (out_dir / "meta.json").write_text(meta_text)
    print(f"Map data from {meta.get('generated_at')}: {len(meta['tiles'])} tiles files")

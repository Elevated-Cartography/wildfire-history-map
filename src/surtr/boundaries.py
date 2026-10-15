"""Work out which states/provinces (and so countries) a fire burned in."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import fiona
from shapely import STRtree
from shapely.geometry import shape

log = logging.getLogger(__name__)

# Coastlines in the boundary data are simplified, so fires right on the coast
# can miss every state. Within this many degrees (~5km) the nearest one wins.
NEAREST_MAX_DISTANCE = 0.05


@dataclass(frozen=True)
class Region:
    code: str  # ISO 3166-2, e.g. "US-CA"
    name: str  # "California"
    country_code: str  # ISO 3166-1 alpha-2, e.g. "US"
    country_name: str  # "United States of America"


class Boundaries:
    def __init__(self, path: Path):
        self.regions: List[Region] = []
        geometries = []
        # Natural Earth admin-1 states and provinces
        with fiona.open(f"zip://{path}") as src:
            for feature in src:
                props = feature["properties"]
                self.regions.append(
                    Region(
                        code=props["iso_3166_2"] or props["adm1_code"],
                        name=props["name"],
                        country_code=props["iso_a2"],
                        country_name=props["admin"],
                    )
                )
                geometries.append(shape(feature["geometry"]))
        self.tree = STRtree(geometries)

    def regions_for(self, geometry) -> List[Region]:
        """The regions a shapely geometry overlaps, sorted by code."""
        hits = self.tree.query(geometry, predicate="intersects")
        if len(hits) == 0:
            hits = self.tree.query_nearest(geometry, max_distance=NEAREST_MAX_DISTANCE)
        return sorted({self.regions[i] for i in hits}, key=lambda r: r.code)

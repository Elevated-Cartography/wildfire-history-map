"""Turn processed fires into PMTiles files, none bigger than a size limit.

One file for everything got too big (400+ MB with Canada) for places with
file size limits, like git (100 MB a file) or Cloudflare Pages (25 MB). So
fires are split into groups by area, each group becomes its own tiles file,
and the site adds one map source per file. Each file records its bounds, so
MapLibre only downloads the files covering what's on screen.
"""

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from subprocess import run
from typing import List, Tuple

# Roughly how many bytes of processed GeoJSON end up as one byte of tiles (it's
# about 10 for this data). Only used to guess group sizes up front: the real
# sizes are checked after tippecanoe runs, and groups that come out too big
# get split again.
GEOJSON_BYTES_PER_TILE_BYTE = 8

# The feature ID in a processed GeoJSON line. Faster than parsing the whole
# line, and a quote inside a string value would be escaped, so this can't
# match inside comments.
ID_PATTERN = re.compile(r'(?<!\\)"id":(\d+)')


@dataclass(frozen=True)
class Fire:
    id: int
    # Center of its bounding box
    x: float
    y: float
    # Bytes of processed GeoJSON
    weight: int
    bounds: Tuple[float, float, float, float]


def split_fires(fires: List[Fire], max_weight: float) -> List[List[Fire]]:
    """Split fires into groups weighing at most `max_weight` (unless a single
    fire is heavier). Each split cuts a group in half by weight across the
    longer side of its extent, like a k-d tree, so groups cover compact areas
    and dense places get split finer than sparse ones."""
    total = sum(f.weight for f in fires)
    if total <= max_weight or len(fires) < 2:
        return [fires]
    xs = [f.x for f in fires]
    ys = [f.y for f in fires]
    by_x = max(xs) - min(xs) >= max(ys) - min(ys)
    ordered = sorted(fires, key=(lambda f: f.x) if by_x else (lambda f: f.y))
    running = 0
    cut = len(ordered) - 1
    for i, fire in enumerate(ordered):
        running += fire.weight
        if running >= total / 2:
            cut = i + 1
            break
    cut = min(max(cut, 1), len(ordered) - 1)
    return split_fires(ordered[:cut], max_weight) + split_fires(ordered[cut:], max_weight)


def group_bounds(fires: List[Fire]) -> List[float]:
    return [
        min(f.bounds[0] for f in fires),
        min(f.bounds[1] for f in fires),
        max(f.bounds[2] for f in fires),
        max(f.bounds[3] for f in fires),
    ]


def write_groups(inputs: List[Path], groups: List[List[Fire]], outputs: List[Path]):
    """Copy each processed GeoJSON line from `inputs` into the output for the
    group its fire is in."""
    group_of = {fire.id: i for i, group in enumerate(groups) for fire in group}
    files = [open(path, "w") for path in outputs]
    try:
        for path in inputs:
            with open(path) as f:
                for line in f:
                    match = ID_PATTERN.search(line)
                    if match and int(match[1]) in group_of:
                        files[group_of[int(match[1])]].write(line)
    finally:
        for file in files:
            file.close()


def run_tippecanoe(tippecanoe: str, inputs: List[Path], output: Path):
    cmd = [
        tippecanoe,
        "-l", "fire",
        "-zg",
        "-P",
        "--use-attribute-for-id=id",
        "--force",
        "--quiet",
        "--output", str(output),
        *map(str, inputs),
    ]
    run(cmd, check=True)


def build_tiles(
    tippecanoe: str, inputs: List[Path], fires: List[Fire], work_dir: Path, max_bytes: int
) -> List[Tuple[Path, List[Fire]]]:
    """Build tiles files for `fires` (whose GeoJSON is in `inputs`) in
    `work_dir`, none bigger than `max_bytes`. Returns (path, fires) for each."""
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    names = (work_dir / f"group-{n}" for n in range(1_000_000))

    groups = split_fires(fires, max_bytes * GEOJSON_BYTES_PER_TILE_BYTE)
    paths = [next(names).with_suffix(".geojsonl") for _ in groups]
    write_groups(inputs, groups, paths)
    pending = list(zip(paths, groups))
    print(f"Building tiles in {len(pending)} parts (at most {max_bytes / 1e6:.0f} MB each)")

    done = []
    while pending:
        geojson, group = pending.pop(0)
        output = geojson.with_suffix(".pmtiles")
        run_tippecanoe(tippecanoe, [geojson], output)
        size = output.stat().st_size
        if size <= max_bytes:
            print(f"  {len(group):,} fires: {size / 1e6:.0f} MB")
            done.append((output, group))
            geojson.unlink()
            continue
        if len(group) < 2:
            raise RuntimeError(
                f"Fire {group[0].id} alone makes {size / 1e6:.0f} MB of tiles, "
                f"more than the {max_bytes / 1e6:.0f} MB limit"
            )
        # Guessed wrong for this area (some data simplifies better than
        # others): split it and try again
        print(f"  {len(group):,} fires: {size / 1e6:.0f} MB is too big, splitting")
        halves = split_fires(group, sum(f.weight for f in group) / 2)
        half_paths = [next(names).with_suffix(".geojsonl") for _ in halves]
        write_groups([geojson], halves, half_paths)
        geojson.unlink()
        output.unlink()
        pending.extend(zip(half_paths, halves))
    return done


def install_tiles(
    built: List[Tuple[Path, List[Fire]]], out_dir: Path, version: str
) -> List[dict]:
    """Move built tiles into `out_dir` as fire-<version>-0.pmtiles,
    fire-<version>-1.pmtiles... (west to east), replacing any from before.
    Returns their entries for meta.json.

    The version in the names means a browser can never mix cached tiles from
    one build with another build's fire list, and a published copy can be
    updated by uploading the new files before the meta.json that points at
    them."""
    for old in out_dir.glob("fire*.pmtiles"):
        old.unlink()
    entries = []
    for i, (path, group) in enumerate(sorted(built, key=lambda b: group_bounds(b[1]))):
        name = f"fire-{version}-{i}.pmtiles"
        size = path.stat().st_size
        shutil.move(path, out_dir / name)
        entries.append({
            "url": name,
            "bounds": [round(v, 4) for v in group_bounds(group)],
            "fires": len(group),
            "bytes": size,
        })
    return entries

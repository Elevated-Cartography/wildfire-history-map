import json
import random

from surtr.tiles import Fire, split_fires, write_groups


def fire(id, x, y, weight=100):
    return Fire(id=id, x=x, y=y, weight=weight, bounds=(x - 0.1, y - 0.1, x + 0.1, y + 0.1))


def test_small_sets_stay_whole():
    fires = [fire(i, i, 0) for i in range(10)]
    assert split_fires(fires, max_weight=10_000) == [fires]


def test_every_fire_lands_in_exactly_one_group_under_the_limit():
    rng = random.Random(1)
    fires = [fire(i, rng.uniform(-125, -60), rng.uniform(25, 70), rng.randint(1, 5000)) for i in range(5000)]
    groups = split_fires(fires, max_weight=200_000)
    ids = [f.id for group in groups for f in group]
    assert sorted(ids) == list(range(5000))
    assert all(sum(f.weight for f in group) <= 200_000 for group in groups)
    assert len(groups) > 1


def test_a_fire_heavier_than_the_limit_gets_a_group_of_its_own():
    fires = [fire(0, 0, 0, weight=1_000), fire(1, 1, 0, weight=10), fire(2, 2, 0, weight=10)]
    groups = split_fires(fires, max_weight=100)
    assert [f.id for f in groups[0]] == [0]
    assert all(sum(f.weight for f in g) <= 100 or len(g) == 1 for g in groups)


def test_groups_follow_geography():
    # Two clusters far apart, each about half the weight: the first cut
    # separates them
    west = [fire(i, -120 + i * 0.01, 40) for i in range(50)]
    east = [fire(100 + i, -75 + i * 0.01, 40) for i in range(50)]
    groups = split_fires(west + east, max_weight=6_000)
    assert len(groups) == 2
    assert {f.id for f in groups[0]} in ({f.id for f in west}, {f.id for f in east})


def test_write_groups_routes_lines_by_feature_id(tmp_path):
    lines = [
        {"type": "Feature", "properties": {"id": 1, "comments": 'said "id":2 here'}, "geometry": None},
        {"type": "Feature", "properties": {"id": 2}, "geometry": None},
        {"type": "Feature", "properties": {"id": 3}, "geometry": None},
    ]
    source = tmp_path / "in.geojsonl"
    source.write_text("".join(json.dumps(line, separators=(",", ":")) + "\n" for line in lines))
    outputs = [tmp_path / "a.geojsonl", tmp_path / "b.geojsonl"]
    write_groups([source], [[fire(1, 0, 0), fire(3, 0, 0)], [fire(2, 0, 0)]], outputs)
    ids = lambda path: [json.loads(line)["properties"]["id"] for line in path.read_text().splitlines()]
    # The quoted "id" in fire 1's comments doesn't confuse the routing
    assert ids(outputs[0]) == [1, 3]
    assert ids(outputs[1]) == [2]


def test_install_tiles_names_files_with_the_version_and_replaces_old_ones(tmp_path):
    from surtr.tiles import install_tiles

    out = tmp_path / "out"
    out.mkdir()
    (out / "fire.pmtiles").write_text("from before partitioning")
    (out / "fire-202501010000-0.pmtiles").write_text("an older build")
    built = []
    for name, x in [("east", -80), ("west", -120)]:
        path = tmp_path / f"{name}.pmtiles"
        path.write_text(name)
        built.append((path, [fire(1 if name == "east" else 2, x, 40)]))
    entries = install_tiles(built, out, "202610150000")
    # West to east
    assert [e["url"] for e in entries] == ["fire-202610150000-0.pmtiles", "fire-202610150000-1.pmtiles"]
    assert (out / "fire-202610150000-0.pmtiles").read_text() == "west"
    assert sorted(p.name for p in out.iterdir()) == ["fire-202610150000-0.pmtiles", "fire-202610150000-1.pmtiles"]

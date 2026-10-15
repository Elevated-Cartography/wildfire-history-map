from tqdm import tqdm

from .build import read_geojsonl
from .reason import NIFCRulesEngine
from .source import Config


def reason_test(config: Config, data_dir):
    """Run every cause combination in the fetched data through the rules
    engine and list the ones that don't match exactly one rule."""
    rules_engine = NIFCRulesEngine()
    layers = [(l, l.fields) for l in config.lookups.values()]
    layers += [(s, s.cause.fields) for s in config.sources if s.cause.fields]
    for layer, fields in layers:
        for feature in tqdm(read_geojsonl(layer.raw_path(data_dir)), desc=layer.name):
            props = feature["properties"]
            rules_engine.match(*(props.get(f) for f in fields))

    for unmatched in sorted(rules_engine.unmatched, key=lambda t: t[::-1]):
        print(unmatched)
    print(f"Total unmatched: {len(rules_engine.unmatched)}")
    for cause, general, specific, reasons in sorted(rules_engine.multiple_matches):
        print(f"{cause} => {general} => {specific}: {[r.name for r in reasons]}")
    print(f"Total multiple matches: {len(rules_engine.multiple_matches)}")

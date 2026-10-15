import argparse
import logging
import sys
from pathlib import Path

from .source import load_config


def main():
    parser = argparse.ArgumentParser(prog="surtr")
    parser.add_argument("-c", "--config", default="sources.toml", type=Path)
    parser.add_argument("-d", "--data-dir", default="data", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="Download any sources that have changed")
    fetch_p.add_argument("names", nargs="*", help="Sources/lookups to fetch (default: all)")
    fetch_p.add_argument("-f", "--force", action="store_true", help="Fetch even if unchanged")

    boundaries_p = sub.add_parser(
        "fetch-boundaries", help="Download the state/province boundaries if missing"
    )
    boundaries_p.add_argument("-f", "--force", action="store_true", help="Download again")

    download_p = sub.add_parser(
        "download-data", help="Download published map data from a GitHub release instead of building it"
    )
    download_p.add_argument("--repo", required=True, help="GitHub repository, as owner/name")
    download_p.add_argument("--tag", default="data", help="Release tag (default: data)")
    download_p.add_argument("-o", "--out-dir", default="build", type=Path)

    sub.add_parser("list", help="Print the names of all sources and lookups")

    build_p = sub.add_parser("build", help="Process fetched data into pmtiles")
    build_p.add_argument("-o", "--out-dir", default="build", type=Path)
    build_p.add_argument("--tippecanoe", help="Path to tippecanoe (default: $TIPPECANOE or PATH)")
    build_p.add_argument(
        "--max-tile-mb",
        type=float,
        default=100,
        help="Split the tiles into files no bigger than this (default: 100, GitHub's file limit)",
    )

    sub.add_parser("reason-test", help="List cause combinations the rules engine can't match")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # httpx logs every request at INFO, which drowns out the progress bars
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = load_config(args.config)

    if args.command == "fetch":
        from .fetch import fetch_layer

        layers = [config.layer(n) for n in args.names] if args.names else config.layers
        for layer in layers:
            fetch_layer(layer, args.data_dir, force=args.force)
    elif args.command == "fetch-boundaries":
        from .fetch import fetch_boundaries

        fetch_boundaries(
            config.boundaries_url, config.boundaries_path(args.data_dir), force=args.force
        )
    elif args.command == "download-data":
        from .fetch import download_data

        download_data(args.repo, args.tag, args.out_dir)
    elif args.command == "list":
        print("\n".join(layer.name for layer in config.layers))
    elif args.command == "build":
        from .build import build

        build(
            config,
            args.data_dir,
            args.out_dir,
            tippecanoe=args.tippecanoe,
            max_tile_mb=args.max_tile_mb,
        )
    elif args.command == "reason-test":
        from .reason_test import reason_test

        reason_test(config, args.data_dir)


if __name__ == "__main__":
    sys.exit(main())

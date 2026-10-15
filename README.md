# surtr

An interactive map of historical wildfire perimeters in the US and Canada, built as a static site
(Vue + MapLibre + PMTiles, on an [OpenFreeMap](https://openfreemap.org/)
basemap, with optional 3D terrain from [Mapterhorn](https://mapterhorn.com/))
that can be hosted on GitHub Pages.

## Running it locally

You'll need [uv](https://docs.astral.sh/uv/), Node 20.19+ or 22.12+ (pinned in
[.node-version](.node-version), so `fnm use` / `nvm use` picks it up) and GNU
make 4.3+. Then:

```sh
make dev DATA_FROM=release   # http://localhost:5173, hot reloads as you edit web/
make preview DATA_FROM=release   # http://localhost:4173, the production build as deployed
```

Either one installs the Python and npm dependencies, and `DATA_FROM=release`
downloads the map data (~0.5 GB) that the [Update data](#deploying) workflow
last published, rather than building it. If the repo is private, set
`GITHUB_TOKEN` (or `GH_TOKEN`) to a token that can read it. `make
download-data` replaces your copy with the latest published one.

### Building the data yourself

Without `DATA_FROM=release`, `make dev` and `make preview` build the data
instead: they download the sources (roughly 4 GB from ArcGIS) and build the
tiles, which takes about 30 minutes the first time. That also builds
[tippecanoe](https://github.com/felt/tippecanoe) into `.tools/` if it isn't on
your `PATH` (that needs a C++ compiler plus sqlite3 and zlib headers;
`apt install build-essential libsqlite3-dev zlib1g-dev`).

After that, `make dev` and `make preview` use the data you already have. To
update it, run `make fetch dev` (or plain `make`): that only downloads sources
that have changed upstream, and only rebuilds tiles when there's new data or
the pipeline code changed. `OFFLINE=1` skips the update check for any target.

Other targets: `make site` (build into `dist/`), `make test`, `make fetch`,
`make tiles`, `make clean`, `make distclean`.

The frontend can also be worked on directly with `npm run dev` in `web/`, once
the tiles exist. `VITE_OFFLINE=1 npm run dev` swaps the basemap for a plain
background if you don't have a network connection.

## How it works

```
sources.toml ──surtr fetch──▶ data/raw/*.geojsonl ──surtr build──▶ web/public/data/fire-*.pmtiles
                                                                   web/public/data/fires.json
                                                                   web/public/data/meta.json
web/ (Vue + Vite) ──vite build──▶ dist/
```

- **`surtr fetch`** ([fetch.py](src/surtr/fetch.py)) queries each ArcGIS
  FeatureServer layer listed in [sources.toml](sources.toml) directly, by object
  ID in parallel chunks, and writes newline-delimited GeoJSON. It compares the
  layer's `dataLastEditDate` against the previous fetch and skips the download
  if nothing changed.
- **`surtr build`** ([build.py](src/surtr/build.py)) normalizes every source to
  a common schema, fills in causes (directly, or via the NIFC rules engine in
  [reason.py](src/surtr/reason.py) joined on IRWIN ID), drops duplicates
  across sources, works out which states/countries each fire burned in
  ([boundaries.py](src/surtr/boundaries.py)), burn time and start month, and
  runs tippecanoe. The tiles are split by area into files of at most 100 MB
  (GitHub's file size limit; `make MAX_TILE_MB=25` for, say, Cloudflare
  Pages), each a separate map source ([tiles.py](src/surtr/tiles.py)). Each
  file records its bounds, so the site only downloads tiles from the files
  covering the view. Its output goes in Vite's public dir,
  so the dev server serves it as-is and `vite build` copies it into `dist/`.
- **The frontend** ([web/](web/)) is a Vue app built with Vite. The map lives
  in [FireMap.vue](web/src/components/FireMap.vue); the basemap style is in
  [basemap.js](web/src/basemap.js).
- **The fire list** under the map reads `fires.json`, every fire's properties
  and bounding box (~4 MB gzipped), because the tiles only hold what's on
  screen and drop small fires at low zooms. The filters are applied twice, as
  a MapLibre expression for the map and a JavaScript function for the list,
  both built in [filterLogic.js](web/src/filterLogic.js). `make test` checks
  they agree.
- **Links**: the map view, the picked fire, the filters, the list scope and 3D
  are kept in the URL hash ([urlState.js](web/src/urlState.js)), so the
  address bar is always a shareable link. Fires are linked by a stable `key`
  from the build (from the IRWIN incident ID where there is one, otherwise
  the source, year, name and location), since the numeric IDs change with
  every data refresh.
- **`surtr reason-test`** lists cause combinations in the fetched data that the
  rules engine can't map to exactly one cause code.
- **GitHub Actions** build the data and deploy the site separately; see
  [Deploying](#deploying).

### Adding a source

Any ArcGIS FeatureServer polygon layer can be added as a `[[sources]]` entry in
`sources.toml` by mapping its fields onto ours. Order matters: when a fire is in
several sources, the first one listed wins.

## Deploying

The site goes on GitHub Pages, with the map data kept out of git (each
version is ~0.5 GB, and git would keep every one):

- **[Update data](.github/workflows/data.yml)** runs weekly (and on demand from
  the Actions tab). It fetches the sources, builds the tiles and publishes
  them as files on the `data` release, replacing the previous build's. The
  files are named with the build version and `meta.json` goes up last, so
  anything downloading in the middle of an update still gets a complete set.
- **[Deploy site](.github/workflows/deploy.yml)** runs on every push to
  `main` and after each data update. It downloads the published data
  (`make site DATA_FROM=release`), builds the site, tests it and deploys it,
  in a couple of minutes.

To set it up: enable Pages under *Settings → Pages → Source: GitHub Actions*,
then run **Update data** once from the Actions tab (the first run takes
around half an hour; later ones skip sources that haven't changed). Until
there's a `data` release, Deploy site fails with a message saying so.

## Data sources

| Source | Coverage | Updated |
| --- | --- | --- |
| [CAL FIRE FRAP Fire Perimeters](https://www.fire.ca.gov/what-we-do/fire-resource-assessment-program/fire-perimeters) | California, 1878–last season | Yearly (spring) |
| [NIFC InterAgency Fire Perimeter History](https://data-nifc.opendata.arcgis.com/datasets/nifc::interagencyfireperimeterhistory-all-years-view) | US, 1800s–last season | Yearly |
| [WFIGS Interagency Fire Perimeters](https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-interagency-fire-perimeters) | US, 2016–today (incl. active fires) | Continuously |
| [WFIGS Incident Locations](https://data-nifc.opendata.arcgis.com/datasets/nifc::wildland-fire-incident-locations) | US incident points, used for causes | Continuously |
| [Canada National Burned Area Composite (NBAC)](https://cwfis.cfs.nrcan.gc.ca/ha/nfdb?type=nbac), via [Esri Canada](https://www.arcgis.com/home/item.html?id=82264f7d8a7548ce820b571a184e997e) | Canada, 1972–last season (no fire names) | Yearly |
| [Natural Earth admin-1 states and provinces](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/) | World, used to tag fires with their states/countries | Rarely |

### Candidates

- **[USGS Combined Wildland Fire Polygons](https://www.sciencebase.gov/catalog/item/61707c2ad34ea36449a6b066)**
  (Welty & Jeffries), 1835–2020. Merges 40 US datasets, including many state
  and agency records not in NIFC. Probably the best way to fill in pre-2000
  history outside California. It's a one-off download (ScienceBase), not a
  live service.
- **[MTBS Burned Area Boundaries](https://www.mtbs.gov/direct-download)**,
  1984–2024. Large fires only, but derived from satellite imagery and linked
  to burn-severity rasters. A severity overlay would be a nice feature.
- **[FPA FOD](https://www.fs.usda.gov/rds/archive/Catalog/RDS-2013-0009.6)**
  (Short), 2.3M fire points 1992–2020 with standardized causes. Could fill in
  causes for perimeters without an IRWIN ID via a space/time join.

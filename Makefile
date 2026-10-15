# surtr: historical wildfire perimeter map
#
#   make dev        Build anything that's missing, then start the Vite dev
#                   server (hot reload) on http://localhost:5173. Add
#                   DATA_FROM=release to download the published map data
#                   rather than building it.
#   make preview    Build the production site and serve it on :4173, to check
#                   exactly what will be deployed
#                   (dev and preview don't check for data updates on their own;
#                   `make fetch dev` does)
#   make site       Build the production site into dist/
#   make test       Run the tests
#   make fetch      Only check for and download updated sources
#   make tiles      Rebuild tiles (also fetches; add OFFLINE=1 to skip that)
#   make download-data
#                   Replace the map data with what's published on GitHub
#   make clean      Remove build outputs (keeps downloaded data)
#   make distclean  Remove downloaded data, node_modules and tools too
#
# Set OFFLINE=1 to skip checking for updates and work with the data you have.
# The map tiles are split into files of at most MAX_TILE_MB (default 100,
# GitHub's file size limit).
# tippecanoe is found on your PATH or via $TIPPECANOE; failing that, it's built
# from source into .tools/ the first time it's needed.
#
# DATA_FROM says where the map data comes from: "build" (the default) runs the
# pipeline here, a 4 GB download and ~20 minute build the first time;
# "release" downloads the ~0.5 GB that the "Update data" workflow last
# published to the DATA_RELEASE release of DATA_REPO (a private repo needs
# $GITHUB_TOKEN). Either way it only happens when there's no map data yet.
# DATA_REPO defaults to the GitHub repo the origin remote points at.

SURTR ?= uv run surtr
MAX_TILE_MB ?= 100
DATA_FROM ?= build
DATA_REPO ?= $(shell git remote get-url origin 2>/dev/null | sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$$##')
DATA_RELEASE ?= data

DATA := data
# Pipeline output goes in Vite's public dir: served as-is in dev, copied into
# dist/ by `vite build`
BUILD := web/public/data
DIST := dist

TIPPECANOE_VERSION := 2.78.0
LOCAL_TIPPECANOE := .tools/tippecanoe-$(TIPPECANOE_VERSION)/tippecanoe
TIPPECANOE ?= $(or $(shell command -v tippecanoe 2>/dev/null),$(LOCAL_TIPPECANOE))
export TIPPECANOE

# Use the project's .venv even if some other virtualenv is active
unexport VIRTUAL_ENV

# Same as `surtr list`, but without needing the venv just to parse this file
LAYERS := $(shell sed -n 's/^name = "\(.*\)"/\1/p' sources.toml)
RAW := $(LAYERS:%=$(DATA)/raw/%.geojsonl)
BOUNDARIES := $(DATA)/reference/admin1.zip
PIPELINE_SRC := sources.toml pyproject.toml $(wildcard src/surtr/*.py)
WEB_SRC := $(shell find web/src web/public/images -type f) \
	web/index.html web/vite.config.js web/package.json web/package-lock.json
NODE_DEPS := web/node_modules/.package-lock.json

.PHONY: all site dev preview test fetch tiles download-data clean distclean check-node FORCE
.DELETE_ON_ERROR:

all: site

## Data

# `make dev` and `make preview` on their own use the data you already have
# rather than checking for updates: WFIGS changes many times a day, and each
# change means a ~5 minute rebuild. Run `make fetch` or `make` to update.
ifneq ($(MAKECMDGOALS),)
ifeq ($(filter-out dev preview,$(MAKECMDGOALS)),)
OFFLINE ?= 1
endif
endif

# Raw files are always "rebuilt", but `surtr fetch` leaves them untouched when
# the source hasn't changed, so make only rebuilds tiles when there's new data.
ifndef OFFLINE
$(RAW): FORCE
endif

$(DATA)/raw/%.geojsonl:
	$(SURTR) fetch $*

# State/province boundaries hardly ever change, so they're only downloaded once
$(BOUNDARIES):
	$(SURTR) fetch-boundaries

fetch: $(RAW) $(BOUNDARIES)

# meta.json lists the rest of the map data: the tiles, split into as many files
# as it takes to keep each under MAX_TILE_MB, and the fire list
ifeq ($(DATA_FROM),release)
$(BUILD)/meta.json:
	$(SURTR) download-data --repo $(DATA_REPO) --tag $(DATA_RELEASE) -o $(BUILD)
else
$(BUILD)/meta.json: $(RAW) $(BOUNDARIES) $(PIPELINE_SRC) | $(TIPPECANOE)
	$(SURTR) build -o $(BUILD) --max-tile-mb $(MAX_TILE_MB)
endif

download-data:
	$(SURTR) download-data --repo $(DATA_REPO) --tag $(DATA_RELEASE) -o $(BUILD)

tiles: $(BUILD)/meta.json

$(LOCAL_TIPPECANOE):
	@echo "tippecanoe not found, building $(TIPPECANOE_VERSION) into .tools/ (needs a C++ compiler, sqlite3 and zlib headers)"
	rm -rf $(@D)
	git clone --quiet --depth 1 --branch $(TIPPECANOE_VERSION) https://github.com/felt/tippecanoe.git $(@D)
	$(MAKE) -C $(@D) -j4 tippecanoe

## Web

# Vite needs a newer Node than a lot of systems have. .node-version pins one
# for fnm/nvm/volta.
check-node:
	@node -e 'const [M, m] = process.versions.node.split(".").map(Number); process.exit(M > 22 || (M == 22 && m >= 12) || (M == 20 && m >= 19) ? 0 : 1)' \
		|| { echo "Vite needs Node 20.19+ or 22.12+, but you have $$(node --version). Try 'fnm use' (see .node-version)."; exit 1; }

$(NODE_DEPS): web/package.json web/package-lock.json | check-node
	cd web && npm ci
	@touch $@

site: $(DIST)/index.html

$(DIST)/index.html: $(WEB_SRC) $(BUILD)/meta.json $(NODE_DEPS) | check-node
	cd web && npm run build

dev: $(BUILD)/meta.json $(NODE_DEPS) | check-node
	cd web && npm run dev

preview: site
	cd web && npm run preview

# The pipeline's tests, then the frontend's (which check the map's filter and
# the fire list's filter agree, on a sample of fires.json when it's been built)
test: $(NODE_DEPS) | check-node
	uv run pytest -q tests
	cd web && npm test

## Cleanup

clean:
	rm -rf $(BUILD) $(DIST) $(DATA)/processed

distclean: clean
	rm -rf $(DATA) web/node_modules .tools

FORCE:

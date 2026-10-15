<script setup>
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre loads its web worker from a file next to its own module, which
// bundling breaks, so point it at a copy that Vite emits
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import * as pmtiles from "pmtiles";
import { markRaw, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { faMountainSun } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { BASEMAPS } from "../basemap.js";
import { TERRAIN_MAX_PITCH, TERRAIN_MAX_ZOOM, TERRAIN_PITCH, TERRAIN_TILEJSON } from "../terrain.js";
import FirePicker from "./FirePicker.vue";
import MeasureTool from "./MeasureTool.vue";

const props = defineProps({
  // MapLibre filter expression for the fire layer
  filter: { type: Array, required: true },
  // Keys into BASEMAPS / DISTANCE_UNITS / AREA_UNITS
  basemap: { type: String, required: true },
  distanceUnit: { type: String, required: true },
  areaUnit: { type: String, required: true },
  terrainExaggeration: { type: Number, default: 1.5 },
  // {center: [lng, lat], zoom, bearing, pitch} to start at, e.g. from a link
  initialView: { type: Object, default: null },
  // The fire tiles files from meta.json: [{url, bounds, ...}] (see tiles.py)
  tiles: { type: Array, default: () => [] },
  // Feature IDs of the fires to highlight
  hoveredId: { type: Number, default: null },
  focusedId: { type: Number, default: null },
});
// hover/focus: a fire's feature ID, or null
// bounds: [west, south, east, north] whenever the map stops moving
// view: {center: [lng, lat], zoom, bearing, pitch} likewise, for links
const emit = defineEmits(["hover", "focus", "bounds", "view"]);
// 3D terrain on or off
const terrain = defineModel("terrain", { type: Boolean, default: false });

maplibregl.setWorkerUrl(maplibreWorkerUrl);

const pmtilesProtocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);

// The fires are split across several tiles files to keep each one small
// (see tiles.py), each its own map source with the same set of layers
const sourceId = (i) => `fires-${i}`;
const layerId = (kind, i) => `fire-${kind}-${i}`;
// e.g. every file's fill layer
const layerIds = (kind) => props.tiles.map((_, i) => layerId(kind, i));

const container = ref(null);
// Deliberately not reactive: Vue's proxies break MapLibre's internals
let map = null;
let scaleControl = null;
let navigationControl = null;
// Whether the current basemap style has loaded, so layers can be added
let styleLoaded = false;
let fireListenersAdded = false;
// The same map, handed to child components once it exists
const mapForTools = shallowRef(null);
const measuring = ref(false);

const hasFireLayers = () => props.tiles.length > 0 && Boolean(map?.getLayer(layerId("fill", 0)));

function setFireState(id, state) {
  if (id == null || !hasFireLayers()) return;
  // Which file a fire's in isn't known here, and setting state on a feature a
  // source doesn't have is harmless, so set it everywhere
  props.tiles.forEach((_, i) => {
    map.setFeatureState({ source: sourceId(i), sourceLayer: "fire", id }, state);
  });
}

// Where fires overlap, the smallest one is most likely the one you meant
function smallestFire(features) {
  return features.reduce(
    (best, f) => (best == null || (f.properties.size ?? Infinity) < (best.properties.size ?? Infinity) ? f : best),
    null,
  );
}

const featureStateIs = (state) => ["boolean", ["feature-state", state], false];

// The layers drawn for each tiles file, by kind
const FIRE_LAYERS = {
  fill: () => ({
    type: "fill",
    filter: props.filter,
    paint: {
      "fill-color": ["case", featureStateIs("focused"), "rgba(0,0,0,0)", "rgba(255,0,0,.3)"],
    },
  }),
  outline: () => ({
    type: "line",
    filter: props.filter,
    paint: { "line-color": "rgb(255,0,0)", "line-width": 1 },
  }),
  // Highlighting ignores the filter, so a fire you're looking at in the
  // table doesn't vanish when you move the year slider
  select: () => ({
    type: "fill",
    paint: {
      "fill-color": ["case", featureStateIs("focused"), "rgba(255,140,0,.8)", "rgba(0,0,0,0)"],
    },
  }),
  highlight: () => ({
    type: "line",
    paint: {
      "line-color": "rgb(150,40,0)",
      "line-width": ["case", ["any", featureStateIs("hovered"), featureStateIs("focused")], 3, 0],
    },
  }),
};

// Switching basemaps replaces the whole style, so this runs on every style
// load (and when the list of tiles files arrives), putting the fire layers and
// their highlight state back
function addFireLayers() {
  if (!styleLoaded || props.tiles.length === 0 || hasFireLayers()) return;
  props.tiles.forEach((tile, i) => {
    // Resolve against the page so this works under a GitHub Pages project path
    const url = new URL(`${import.meta.env.BASE_URL}data/${tile.url}`, document.baseURI);
    map.addSource(sourceId(i), {
      type: "vector",
      // Each file records its bounds, so MapLibre only fetches tiles from the
      // files covering the view
      url: `pmtiles://${url}`,
      attribution: "Fire perimeters: CAL FIRE FRAP, NIFC, Natural Resources Canada",
    });
  });
  // Draw the fires under the basemap's labels so place names stay readable.
  // Layers go in by kind (every fill, then every outline...) so one file's
  // fires never cover another's highlights.
  const beforeId = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
  for (const [kind, layer] of Object.entries(FIRE_LAYERS)) {
    props.tiles.forEach((_, i) => {
      map.addLayer(
        { id: layerId(kind, i), source: sourceId(i), "source-layer": "fire", ...layer() },
        beforeId,
      );
    });
  }
  // Listeners on layers outlive the layers, so they only need adding once
  if (!fireListenersAdded) {
    map.on("mousemove", layerIds("fill"), onFireMouseMove);
    map.on("mouseleave", layerIds("fill"), onFireMouseLeave);
    fireListenersAdded = true;
  }

  setFireState(props.hoveredId, { hovered: true });
  setFireState(props.focusedId, { focused: true });
}

// MapLibre keeps the center fixed when the map resizes, so when the results
// panel opens everything would jump up, including the fire you just clicked.
// Pan by half the change to keep the top edge fixed instead.
let lastHeight = null;
function onResize() {
  const height = map.getContainer().clientHeight;
  if (lastHeight != null && height !== lastHeight) {
    map.panBy([0, (lastHeight - height) / -2], { animate: false });
  }
  lastHeight = height;
}

// Mapterhorn elevation, for 3D terrain plus hillshading. They get separate
// sources because MapLibre renders both better that way.
function applyTerrain() {
  if (terrain.value) {
    for (const id of ["terrain", "hillshade"]) {
      if (!map.getSource(id)) {
        map.addSource(id, { type: "raster-dem", url: TERRAIN_TILEJSON, maxzoom: TERRAIN_MAX_ZOOM });
      }
    }
    if (!map.getLayer("hillshade")) {
      // Under the fires so they stay easy to read, or under the labels if the
      // fires haven't been added yet (they go in under the labels too, so
      // they'll end up above this)
      map.addLayer(
        {
          id: "hillshade",
          type: "hillshade",
          source: "hillshade",
          paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "rgba(0,0,0,.4)" },
        },
        hasFireLayers()
          ? layerId("fill", 0)
          : map.getStyle().layers.find((l) => l.type === "symbol")?.id,
      );
    }
    map.setTerrain({ source: "terrain", exaggeration: props.terrainExaggeration });
  } else {
    map.setTerrain(null);
    if (map.getLayer("hillshade")) {
      map.removeLayer("hillshade");
    }
  }
}

// 3D gets a tilted view, rotation and a compass. Flat mode keeps the map
// north-up and untilted, so dragging always just pans.
function applyCameraControls(animate) {
  if (terrain.value) {
    map.setMaxPitch(TERRAIN_MAX_PITCH);
    map.dragRotate.enable();
    map.touchZoomRotate.enableRotation();
    map.keyboard.enableRotation();
    if (!navigationControl) {
      navigationControl = new maplibregl.NavigationControl({ visualizePitch: true });
      map.addControl(navigationControl, "bottom-right");
    }
    if (animate) {
      map.easeTo({ pitch: TERRAIN_PITCH });
    }
  } else {
    map.dragRotate.disable();
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    if (navigationControl) {
      map.removeControl(navigationControl);
      navigationControl = null;
    }
    if (animate) {
      map.easeTo({ pitch: 0, bearing: 0 });
      // Lock the tilt once the map has leveled out (setting it now would jump)
      map.once("moveend", () => {
        if (!terrain.value) map.setMaxPitch(0);
      });
    } else {
      map.setMaxPitch(0);
    }
  }
}

function onStyleLoad() {
  styleLoaded = true;
  addFireLayers();
  applyTerrain();
}

// The menu for choosing between overlapping fires: {fires, x, y} or null
const picker = shallowRef(null);

function onClick(e) {
  picker.value = null;
  if (measuring.value) return;
  if (!hasFireLayers()) return;
  const features = map.queryRenderedFeatures(e.point, { layers: layerIds("fill") });
  // The same fire can come back once per tile it's in. Plain objects for the
  // menu: MapLibre features carry a lot of internal state.
  const fires = [...new Map(features.map((f) => [f.id, { id: f.id, properties: { ...f.properties } }])).values()];
  if (fires.length > 1) {
    // Smallest first: it's the one that's hardest to click on its own
    fires.sort((a, b) => (a.properties.size ?? Infinity) - (b.properties.size ?? Infinity));
    picker.value = { fires, x: e.point.x, y: e.point.y };
  } else {
    emit("focus", fires[0]?.id ?? null);
  }
}

function pickFire(id) {
  picker.value = null;
  emit("focus", id);
}

function emitBounds() {
  emit("bounds", map.getBounds().toArray().flat());
  const center = map.getCenter();
  emit("view", {
    center: [center.lng, center.lat],
    zoom: map.getZoom(),
    bearing: map.getBearing(),
    pitch: map.getPitch(),
  });
}

// Move straight to a {center, zoom, bearing, pitch} view, e.g. from a link
function jumpTo(view) {
  map?.jumpTo(view);
}

// Fit the map to a [west, south, east, north] box, e.g. a fire from the list
function fitBounds(bbox) {
  map?.fitBounds(bbox, { padding: 60, maxZoom: 13 });
}

defineExpose({ fitBounds, jumpTo });

function onFireMouseMove(e) {
  if (measuring.value) return;
  map.getCanvas().style.cursor = "pointer";
  const id = smallestFire(e.features)?.id ?? null;
  if (id !== props.hoveredId) {
    emit("hover", id);
  }
}

function onFireMouseLeave() {
  if (measuring.value) return;
  map.getCanvas().style.cursor = "";
  emit("hover", null);
}

onMounted(() => {
  map = new maplibregl.Map({
    container: container.value,
    style: BASEMAPS[props.basemap].style,
    center: [-119, 37],
    zoom: 6,
    pitch: terrain.value ? TERRAIN_PITCH : 0,
    ...props.initialView,
  });
  applyCameraControls(false);
  scaleControl = new maplibregl.ScaleControl({ unit: props.distanceUnit });
  map.addControl(scaleControl, "bottom-left");
  map.on("style.load", onStyleLoad);
  map.on("click", onClick);
  // The picker's anchored to where you clicked, so it goes once the map moves
  map.on("movestart", () => (picker.value = null));
  map.on("resize", onResize);
  map.on("load", emitBounds);
  map.on("moveend", emitBounds);
  lastHeight = container.value.clientHeight;
  mapForTools.value = markRaw(map);
});

onBeforeUnmount(() => {
  mapForTools.value = null;
  map?.remove();
  map = null;
});

watch(
  () => props.filter,
  (filter) => {
    if (!hasFireLayers()) return;
    for (const id of [...layerIds("fill"), ...layerIds("outline")]) {
      map.setFilter(id, filter);
    }
  },
);

// meta.json (with the list of tiles files) loads after the map's created
watch(() => props.tiles, addFireLayers);

watch(
  () => props.basemap,
  (basemap) => {
    styleLoaded = false;
    map?.setStyle(BASEMAPS[basemap].style, { diff: false });
  },
);

watch(terrain, () => {
  // Not isStyleLoaded(): that's also false while any tiles are loading. If
  // the style isn't ready yet, style.load does it.
  if (styleLoaded) {
    applyTerrain();
  }
  applyCameraControls(true);
});

watch(
  () => props.terrainExaggeration,
  (exaggeration) => {
    if (terrain.value && map?.getSource("terrain")) {
      map.setTerrain({ source: "terrain", exaggeration });
    }
  },
);

watch(
  () => props.distanceUnit,
  (unit) => scaleControl?.setUnit(unit),
);

watch(
  () => props.hoveredId,
  (id, oldId) => {
    setFireState(oldId, { hovered: false });
    setFireState(id, { hovered: true });
  },
);

watch(
  () => props.focusedId,
  (id, oldId) => {
    setFireState(oldId, { focused: false });
    setFireState(id, { focused: true });
  },
);
</script>

<template>
  <div class="map-wrapper">
    <div ref="container" class="map"></div>
    <div class="map-tools">
      <div class="maplibregl-ctrl maplibregl-ctrl-group">
        <button
          type="button"
          :class="{ active: terrain }"
          :aria-pressed="terrain"
          title="3D terrain"
          @click="terrain = !terrain"
        >
          <FontAwesomeIcon :icon="faMountainSun" />
        </button>
      </div>
      <MeasureTool
        v-if="mapForTools"
        v-model:active="measuring"
        :map="mapForTools"
        :distance-unit="distanceUnit"
        :area-unit="areaUnit"
      />
    </div>
    <FirePicker
      v-if="picker"
      :key="`${picker.x},${picker.y}`"
      :fires="picker.fires"
      :x="picker.x"
      :y="picker.y"
      :area-unit="areaUnit"
      @pick="pickFire"
      @hover="emit('hover', $event)"
      @close="picker = null"
    />
  </div>
</template>

<style scoped>
.map-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
}

/* Our own buttons, styled like MapLibre's controls */
.map-tools {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.map-tools .maplibregl-ctrl {
  margin: 0;
}

.maplibregl-ctrl-group button.active {
  background-color: #1565c0;
  color: #fff;
}

.map {
  position: absolute;
  inset: 0;
  background-color: #e5e5e5;
}
</style>

<script setup>
import { faRuler } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { area } from "@turf/area";
import { length } from "@turf/length";
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { formatArea, formatDistance } from "../units.js";

const props = defineProps({
  // The MapLibre map, once it exists
  map: { type: Object, default: null },
  distanceUnit: { type: String, required: true },
  areaUnit: { type: String, required: true },
});
const active = defineModel("active", { type: Boolean, default: false });

const SOURCE_ID = "measure";
// How close (in pixels) a click has to be to an existing point to count as on it
const SNAP_DISTANCE = 8;

const points = shallowRef([]); // [[lng, lat], ...]
const cursor = shallowRef(null); // where the mouse is, for the rubber-band segment
const closed = ref(false); // clicked back on the first point: measuring an area
const finished = ref(false); // double-clicked: done adding points

const lineCoordinates = computed(() => {
  const coords = [...points.value];
  if (closed.value) {
    coords.push(points.value[0]);
  } else if (!finished.value && cursor.value && coords.length > 0) {
    coords.push(cursor.value);
  }
  return coords;
});

const distance = computed(() =>
  lineCoordinates.value.length < 2
    ? 0
    : length(lineFeature(lineCoordinates.value), { units: "meters" }),
);

const areaSquareMeters = computed(() =>
  closed.value ? area(polygonFeature(points.value)) : null,
);

const hint = computed(() => {
  if (closed.value || finished.value) {
    return "Click to start again, Esc to clear";
  }
  if (points.value.length >= 3) {
    return "Click the first point to measure area, double-click to finish";
  }
  return "Click to add points, double-click to finish";
});

function lineFeature(coordinates) {
  return { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates } };
}

function polygonFeature(coordinates) {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [[...coordinates, coordinates[0]]] },
  };
}

const geojson = computed(() => {
  const features = points.value.map((coordinates) => ({
    type: "Feature",
    properties: {},
    geometry: { type: "Point", coordinates },
  }));
  if (lineCoordinates.value.length >= 2) {
    features.push(lineFeature(lineCoordinates.value));
  }
  if (closed.value) {
    features.push(polygonFeature(points.value));
  }
  return { type: "FeatureCollection", features };
});

function clear() {
  points.value = [];
  cursor.value = null;
  closed.value = false;
  finished.value = false;
}

function isNear(screenPoint, lngLat) {
  const projected = props.map.project(lngLat);
  return Math.hypot(projected.x - screenPoint.x, projected.y - screenPoint.y) < SNAP_DISTANCE;
}

function onClick(e) {
  if (!active.value) return;
  if (closed.value || finished.value) {
    clear();
  }
  const current = points.value;
  if (current.length >= 3 && isNear(e.point, current[0])) {
    closed.value = true;
    return;
  }
  if (current.length > 0 && isNear(e.point, current[current.length - 1])) {
    // The second click of a double-click lands on the point the first one added
    finished.value = current.length >= 2;
    return;
  }
  points.value = [...current, [e.lngLat.lng, e.lngLat.lat]];
}

function onMouseMove(e) {
  if (active.value && !closed.value && !finished.value) {
    cursor.value = [e.lngLat.lng, e.lngLat.lat];
  }
}

function onKeyDown(e) {
  if (e.key !== "Escape") return;
  if (points.value.length > 0) {
    clear();
  } else {
    active.value = false;
  }
}

// Switching basemaps replaces the whole style, so this runs on every style load
function addLayers() {
  const map = props.map;
  if (map.getSource(SOURCE_ID)) return;
  map.addSource(SOURCE_ID, { type: "geojson", data: geojson.value });
  map.addLayer({
    id: "measure-fill",
    type: "fill",
    source: SOURCE_ID,
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": "rgba(21,101,192,.15)" },
  });
  map.addLayer({
    id: "measure-line",
    type: "line",
    source: SOURCE_ID,
    filter: ["==", ["geometry-type"], "LineString"],
    paint: { "line-color": "#1565c0", "line-width": 2, "line-dasharray": [2, 1] },
  });
  map.addLayer({
    id: "measure-points",
    type: "circle",
    source: SOURCE_ID,
    filter: ["==", ["geometry-type"], "Point"],
    paint: {
      "circle-radius": 4,
      "circle-color": "#fff",
      "circle-stroke-color": "#1565c0",
      "circle-stroke-width": 2,
    },
  });
}

watch(geojson, (data) => props.map?.getSource(SOURCE_ID)?.setData(data));

watch(
  () => props.map,
  (map, oldMap) => {
    oldMap?.off("style.load", addLayers);
    oldMap?.off("click", onClick);
    oldMap?.off("mousemove", onMouseMove);
    if (!map) return;
    map.on("style.load", addLayers);
    map.on("click", onClick);
    map.on("mousemove", onMouseMove);
    if (map.isStyleLoaded()) {
      addLayers();
    }
  },
  { immediate: true },
);

watch(active, (isActive) => {
  const map = props.map;
  if (isActive) {
    map.getCanvas().style.cursor = "crosshair";
    // Double-click finishes a measurement instead of zooming
    map.doubleClickZoom.disable();
    window.addEventListener("keydown", onKeyDown);
  } else {
    clear();
    map.getCanvas().style.cursor = "";
    map.doubleClickZoom.enable();
    window.removeEventListener("keydown", onKeyDown);
  }
});

onBeforeUnmount(() => window.removeEventListener("keydown", onKeyDown));
</script>

<template>
  <div class="measure-tool">
    <div class="maplibregl-ctrl maplibregl-ctrl-group" style="margin: 0">
      <button
        type="button"
        :class="{ active }"
        :aria-pressed="active"
        title="Measure distance and area"
        @click="active = !active"
      >
        <FontAwesomeIcon :icon="faRuler" />
      </button>
    </div>
    <div v-if="active" class="readout">
      <template v-if="points.length > 0">
        <div><strong>Distance:</strong> {{ formatDistance(distance, distanceUnit) }}</div>
        <div v-if="closed"><strong>Area:</strong> {{ formatArea(areaSquareMeters, areaUnit) }}</div>
      </template>
      <div class="hint">{{ points.length > 0 ? hint : "Click on the map to start measuring" }}</div>
    </div>
  </div>
</template>

<style scoped>
/* Positioned by FireMap's .map-tools */
.measure-tool {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.maplibregl-ctrl-group button.active {
  background-color: #1565c0;
  color: #fff;
}

.readout {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.1);
  padding: 6px 10px;
  font-size: 0.9em;
  min-width: 180px;
}

.hint {
  color: #666;
  font-size: 0.85em;
  margin-top: 2px;
}
</style>

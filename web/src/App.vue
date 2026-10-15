<script setup>
import {
  faCheck,
  faCircleInfo,
  faGear,
  faLink,
} from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import AboutDialog from "./components/AboutDialog.vue";
import FilterPanel from "./components/FilterPanel.vue";
import FireMap from "./components/FireMap.vue";
import ResultsPanel from "./components/ResultsPanel.vue";
import ResultsTable from "./components/ResultsTable.vue";
import SettingsDialog from "./components/SettingsDialog.vue";
import { bboxesOverlap, loadFireList } from "./fireList.js";
import {
  activeFilterCount,
  filterDefaults,
  filterExpression,
  filterPredicate,
  filters,
  initFilters,
  resetFilters,
  setFilters,
} from "./filters.js";
import { LIST_SCOPES, settings } from "./settings.js";
import { formatArea } from "./units.js";
import {
  filtersToParams,
  formatView,
  paramsToFilters,
  parseHash,
  parseView,
  serializeHash,
  settingsFromParams,
  settingsToParams,
} from "./urlState.js";

const logoUrl = `${import.meta.env.BASE_URL}images/surtr.svg`;

// Written by `surtr build`: years present, data sources and when they were
// fetched, and the countries/states fires are in
const meta = ref(null);
// Every fire's properties and bounding box (fires.json), for the list. Big,
// so it's loaded after the map and kept out of Vue's deep reactivity.
const fireList = shallowRef(null);
// [west, south, east, north] of the map view
const viewBounds = shallowRef(null);

// Feature IDs of the fires being pointed at / picked out, shared between the
// map and the list
const hoveredId = ref(null);
const focusedId = ref(null);

const mapRef = ref(null);
const panelCollapsed = ref(false);
const aboutOpen = ref(false);
const settingsOpen = ref(false);

// --- Links: the view, the picked fire, filters and some settings live in the
// URL hash (see urlState.js) ---------------------------------------------------

const URL_DELAY_MS = 300;
const linkParams = parseHash(window.location.hash);
// Before the map's created, so a 3D link opens in 3D
Object.assign(settings, settingsFromParams(linkParams));
const initialView = parseView(linkParams.get("map"));
const mapView = shallowRef(initialView);
// The URL isn't written until a link's been fully applied, or it'd lose the
// parts that can't be applied until the data loads
let linkApplied = false;

onMounted(async () => {
  window.addEventListener("hashchange", onHashChange);
  const response = await fetch(`${import.meta.env.BASE_URL}data/meta.json`);
  meta.value = await response.json();
  initFilters(meta.value);
  setFilters(paramsToFilters(linkParams, filterDefaults(), meta.value));
  // Named with the build version, like the tiles (see install_tiles in tiles.py)
  const fireListFile = meta.value.fire_list ?? "fires.json";
  fireList.value = await loadFireList(`${import.meta.env.BASE_URL}data/${fireListFile}`);
  // With no map position in the link, go to the fire
  focusLinkedFire(linkParams.get("fire"), !initialView);
  linkApplied = true;
  writeUrl();
});

onBeforeUnmount(() => window.removeEventListener("hashchange", onHashChange));

function focusLinkedFire(key, zoom) {
  const list = fireList.value;
  const i = key ? list?.indexByKey.get(key) : undefined;
  focusedId.value = i == null ? null : list.columns.id[i];
  if (i != null && zoom) {
    mapRef.value.fitBounds(list.columns.bbox[i]);
  }
}

// A link pasted into the address bar of an already open page
function onHashChange() {
  const params = parseHash(window.location.hash);
  Object.assign(settings, settingsFromParams(params));
  if (meta.value) {
    setFilters(paramsToFilters(params, filterDefaults(), meta.value));
  }
  const view = parseView(params.get("map"));
  if (view) {
    mapRef.value.jumpTo(view);
  }
  focusLinkedFire(params.get("fire"), !view);
}

const focusedKey = computed(() => {
  const list = fireList.value;
  const i = focusedId.value == null ? undefined : list?.indexById.get(focusedId.value);
  return i == null ? null : list.columns.key[i];
});

function currentHash() {
  const params = new Map();
  if (mapView.value) params.set("map", formatView(mapView.value));
  if (focusedKey.value) params.set("fire", focusedKey.value);
  for (const [key, value] of filtersToParams(filters, filterDefaults())) params.set(key, value);
  for (const [key, value] of settingsToParams(settings)) params.set(key, value);
  return serializeHash(params);
}

function updateUrlNow() {
  clearTimeout(urlTimer);
  const hash = currentHash();
  // replaceState, not pushState: panning around shouldn't fill the back button
  // history, and it doesn't fire hashchange
  history.replaceState(
    null,
    "",
    hash ? `#${hash}` : window.location.pathname + window.location.search,
  );
}

let urlTimer = null;
function writeUrl() {
  clearTimeout(urlTimer);
  urlTimer = setTimeout(updateUrlNow, URL_DELAY_MS);
}

watch(
  [mapView, focusedKey, filters, () => settings.listScope, () => settings.terrain],
  () => {
    if (linkApplied) writeUrl();
  },
  { deep: true },
);

const linkCopied = ref(false);
async function copyLink() {
  updateUrlNow();
  try {
    await navigator.clipboard.writeText(window.location.href);
    linkCopied.value = true;
    setTimeout(() => (linkCopied.value = false), 2000);
  } catch {
    // No clipboard access (e.g. not served over https): let them copy it
    window.prompt("Copy this link:", window.location.href);
  }
}

// Indexes of every fire matching the filters
const matchingIndices = computed(() => {
  const list = fireList.value;
  if (!list) return [];
  const matches = filterPredicate.value;
  const indices = [];
  for (let i = 0; i < list.count; i++) {
    if (matches(list.columns, i)) indices.push(i);
  }
  return indices;
});

// What the list shows: the matching fires in view or everywhere
const listIndices = computed(() => {
  const list = fireList.value;
  if (!list) return [];
  if (settings.listScope === "view") {
    // Until the map says what's in view, there's no list (rather than briefly
    // listing everything, which also throws off scrolling to a linked fire)
    const bounds = viewBounds.value;
    if (!bounds) return [];
    return matchingIndices.value.filter((i) => bboxesOverlap(list.columns.bbox[i], bounds));
  }
  return matchingIndices.value;
});

// Re-sorting a list of 100k+ fires takes a few hundred milliseconds, so the
// table catches up once the list stops changing (say, when a slider is let
// go) instead of on every step. The map and the summary update straight away.
const TABLE_DELAY_MS = 150;
const tableIndices = shallowRef([]);
let tableTimer = null;
watch(
  listIndices,
  (indices) => {
    clearTimeout(tableTimer);
    tableTimer = setTimeout(() => (tableIndices.value = indices), TABLE_DELAY_MS);
  },
  { immediate: true },
);

const summary = computed(() => {
  const list = fireList.value;
  if (!list || (settings.listScope === "view" && !viewBounds.value)) return "Loading fire list…";
  let total = 0;
  for (const i of listIndices.value) total += list.columns.size[i] ?? 0;
  const count = listIndices.value.length;
  return `${count.toLocaleString()} ${count === 1 ? "fire" : "fires"} · ${formatArea(total, settings.areaUnit)}`;
});

const emptyMessage = computed(() => {
  if (settings.listScope === "view") {
    return viewBounds.value ? "No fires match the filters in this part of the map." : "Loading fire list…";
  }
  return "No fires match the filters.";
});

// Picking a fire on the map highlights it in the list, opening the list if
// it's collapsed
function focusFromMap(id) {
  focusedId.value = id;
  if (id != null) {
    panelCollapsed.value = false;
  }
}

function bboxOf(id) {
  const list = fireList.value;
  const i = list?.indexById.get(id);
  return i == null ? null : list.columns.bbox[i];
}

function zoomTo(id) {
  focusedId.value = id;
  const bbox = bboxOf(id);
  if (bbox) mapRef.value.fitBounds(bbox);
}

// Picking a fire in the list highlights it, and brings it into view if it's
// off the map (which can happen when the list shows fires everywhere)
function focusFromList(id) {
  focusedId.value = id;
  const bbox = bboxOf(id);
  if (bbox && viewBounds.value && !bboxesOverlap(bbox, viewBounds.value)) {
    mapRef.value.fitBounds(bbox);
  }
}
</script>

<template>
  <aside class="sidebar">
    <header class="site-header">
      <img :src="logoUrl" alt="" class="logo" />
      <h1>Wildfire History</h1>
      <button type="button" class="icon-button" title="Copy a link to this view" @click="copyLink">
        <FontAwesomeIcon :icon="linkCopied ? faCheck : faLink" />
      </button>
      <span v-if="linkCopied" class="copied" role="status">Link copied</span>
      <button type="button" class="icon-button" title="About" @click="aboutOpen = true">
        <FontAwesomeIcon :icon="faCircleInfo" />
      </button>
      <button type="button" class="icon-button" title="Settings" @click="settingsOpen = true">
        <FontAwesomeIcon :icon="faGear" />
      </button>
    </header>

    <FilterPanel :meta="meta" :fire-list="fireList" @pick="zoomTo" />
  </aside>

  <main class="main">
    <FireMap
      ref="mapRef"
      :initial-view="initialView"
      :tiles="meta?.tiles ?? []"
      :filter="filterExpression"
      :basemap="settings.basemap"
      :distance-unit="settings.distanceUnit"
      :area-unit="settings.areaUnit"
      v-model:terrain="settings.terrain"
      :terrain-exaggeration="settings.terrainExaggeration"
      :hovered-id="hoveredId"
      :focused-id="focusedId"
      @hover="hoveredId = $event"
      @focus="focusFromMap"
      @bounds="viewBounds = $event"
      @view="mapView = $event"
    />
    <ResultsPanel v-model:collapsed="panelCollapsed" title="Fires">
      <template #header>
        <div class="scope" role="radiogroup" aria-label="Which fires to list">
          <label v-for="(label, key) in LIST_SCOPES" :key="key" :class="{ checked: settings.listScope === key }">
            <input v-model="settings.listScope" type="radio" name="list-scope" :value="key" />
            {{ label }}
          </label>
        </div>
        <span class="summary">{{ summary }}</span>
      </template>
      <ResultsTable
        v-if="fireList"
        :fire-list="fireList"
        :indices="tableIndices"
        :hovered-id="hoveredId"
        :focused-id="focusedId"
        :empty-message="emptyMessage"
        @hover="hoveredId = $event"
        @focus="focusFromList"
        @zoom="zoomTo"
      >
        <template #empty>
          <button v-if="activeFilterCount > 0" type="button" class="empty-clear" @click="resetFilters">
            Clear filters
          </button>
        </template>
      </ResultsTable>
      <p v-else class="loading">Loading fire list…</p>
    </ResultsPanel>
  </main>

  <AboutDialog v-model:open="aboutOpen" :meta="meta" />
  <SettingsDialog v-model:open="settingsOpen" />
</template>

<style scoped>
.sidebar {
  flex: 0 0 280px;
  height: 100vh;
  overflow-y: auto;
  background-color: #f1f1f1;
  padding: 12px 16px 20px;
  box-sizing: border-box;
  border-right: 1px solid #ccc;
}

.site-header {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.copied {
  position: absolute;
  top: 36px;
  right: 0;
  z-index: 5;
  padding: 3px 8px;
  border-radius: 4px;
  background: #333;
  color: #fff;
  font-size: 0.8em;
}

.logo {
  width: 28px;
  height: 28px;
}

h1 {
  flex: 1;
  margin: 0;
  font-size: 1.2em;
}

.main {
  flex: 1;
  min-width: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Segmented control for In view / Everywhere */
.scope {
  display: inline-flex;
  border: 1px solid #bbb;
  border-radius: 4px;
  overflow: hidden;
}

.scope label {
  /* Positioning parent for the hidden radio, see .chip in FilterPanel.vue */
  position: relative;
  padding: 2px 10px;
  font-size: 0.9em;
  cursor: pointer;
  user-select: none;
}

.scope label + label {
  border-left: 1px solid #bbb;
}

.scope label.checked {
  background: #c62828;
  color: #fff;
}

.scope input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.scope label:focus-within {
  outline: 2px solid #1565c0;
  outline-offset: -2px;
}

.summary {
  color: #555;
  font-size: 0.9em;
}

.empty-clear {
  padding: 3px 12px;
  border: 1px solid #c62828;
  border-radius: 4px;
  background: #fff;
  color: #c62828;
  font: inherit;
  font-size: 0.9em;
  cursor: pointer;
}

.empty-clear:hover {
  background: #c62828;
  color: #fff;
}

.loading {
  margin: 12px;
  color: #666;
}
</style>

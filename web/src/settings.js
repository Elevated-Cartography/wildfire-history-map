import { reactive, watch } from "vue";
import { BASEMAPS, DEFAULT_BASEMAP } from "./basemap.js";
import { TERRAIN_EXAGGERATIONS } from "./terrain.js";
import { AREA_UNITS, DISTANCE_UNITS } from "./units.js";

const STORAGE_KEY = "surtr-settings";

// Which fires the list shows when nothing's been clicked
export const LIST_SCOPES = {
  view: "In view",
  all: "Everywhere",
};

const DEFAULTS = {
  basemap: DEFAULT_BASEMAP,
  areaUnit: "acres",
  distanceUnit: "imperial",
  listScope: "view",
  terrain: false,
  terrainExaggeration: 1.5,
};

// Which options each setting accepts, so stale saved values (say, a basemap
// that's since been removed) fall back to the default
const CHOICES = {
  basemap: BASEMAPS,
  areaUnit: AREA_UNITS,
  distanceUnit: DISTANCE_UNITS,
  listScope: LIST_SCOPES,
  terrain: { true: true, false: false },
  terrainExaggeration: TERRAIN_EXAGGERATIONS,
};

function load() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? {};
  } catch {
    // Storage blocked (private browsing etc.) or garbage in it: use defaults
  }
  return Object.fromEntries(
    Object.entries(DEFAULTS).map(([key, fallback]) => [
      key,
      saved[key] in CHOICES[key] ? saved[key] : fallback,
    ]),
  );
}

// User settings, saved in this browser's localStorage
export const settings = reactive(load());

watch(
  settings,
  (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      // Not being able to save settings isn't worth bothering anyone about
    }
  },
  { deep: true },
);

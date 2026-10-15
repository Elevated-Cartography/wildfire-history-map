import { computed, reactive } from "vue";
import {
  DURATION_STOPS,
  MIN_YEAR,
  SIZE_STOPS,
  buildFilterExpression,
  buildFilterPredicate,
} from "./filterLogic.js";
import { settings } from "./settings.js";

export { DURATION_STOPS, MIN_YEAR, SIZE_STOPS };

export const FIRE_KINDS = {
  wildfire: "Wildfires",
  prescribed: "Prescribed burns",
};

// Multi-select filters come in two flavors: short "include" lists that start
// with everything checked (kinds, sources), where unchecking hides things, and
// long "narrow down" lists that start empty (causes, months, places), where
// empty means everything.
function defaults(maxYear, sourceNames) {
  return {
    name: "",
    years: [MIN_YEAR, maxYear],
    // Indexes into SIZE_STOPS / DURATION_STOPS
    size: [0, SIZE_STOPS.acres.length - 1],
    duration: [0, DURATION_STOPS.length - 1],
    countries: [],
    regions: [],
    months: [],
    causes: [],
    kinds: ["wildfire"],
    sources: [...sourceNames],
  };
}

let maxYear = new Date().getFullYear();
let sourceNames = [];

export const filters = reactive(defaults(maxYear, sourceNames));

// Once meta.json loads we know the real year range and sources
export function initFilters(meta) {
  maxYear = meta.max_year;
  sourceNames = meta.sources.map((s) => s.name);
  Object.assign(filters, defaults(maxYear, sourceNames));
}

export function resetFilters() {
  Object.assign(filters, defaults(maxYear, sourceNames));
}

// The default filter state, e.g. to leave defaults out of links
export function filterDefaults() {
  return defaults(maxYear, sourceNames);
}

// Replace the whole filter state, e.g. from a link
export function setFilters(state) {
  Object.assign(filters, state);
}

const sameList = (a, b) => a.length === b.length && a.every((v) => b.includes(v));

// Which filter groups differ from their defaults, for badges and "Reset"
export const activeFilters = computed(() => {
  const d = defaults(maxYear, sourceNames);
  return {
    name: filters.name.trim() !== "",
    years: !sameList(filters.years, d.years),
    size: !sameList(filters.size, d.size),
    duration: !sameList(filters.duration, d.duration),
    location: filters.countries.length + filters.regions.length,
    months: filters.months.length,
    causes: filters.causes.length,
    kinds: !sameList(filters.kinds, d.kinds),
    sources: !sameList(filters.sources, d.sources),
  };
});

export const activeFilterCount = computed(
  () => Object.values(activeFilters.value).filter(Boolean).length,
);

// The MapLibre filter expression for the fire layers
export const filterExpression = computed(() => buildFilterExpression(filters, settings.areaUnit));

// (columns, i) => whether fire i in fires.json matches, for the fire list
export const filterPredicate = computed(() => buildFilterPredicate(filters, settings.areaUnit));

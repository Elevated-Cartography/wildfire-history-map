<script setup>
import { computed, ref, watch } from "vue";
import VueSlider from "vue-slider-component";
import "vue-slider-component/theme/default.css";
import { REASON_CODES, SOURCE_LABELS } from "../constants.js";
import { toTitleCase } from "../util.js";
import {
  DURATION_STOPS,
  FIRE_KINDS,
  MIN_YEAR,
  SIZE_STOPS,
  activeFilterCount,
  activeFilters,
  filters,
  resetFilters,
} from "../filters.js";
import { settings } from "../settings.js";
import { AREA_UNITS, formatArea } from "../units.js";
import ControlSection from "./ControlSection.vue";

const props = defineProps({
  // meta.json from `surtr build`, null until it loads
  meta: { type: Object, default: null },
  // fires.json (see fireList.js), null until it loads, for search suggestions
  fireList: { type: Object, default: null },
});
// pick: the feature ID of a fire chosen from the search suggestions
const emit = defineEmits(["pick"]);

// --- Search: typing filters the map, and suggests fires to jump to ---------

const MAX_SUGGESTIONS = 8;
const searchOpen = ref(false);
const activeSuggestion = ref(-1);

// Exact name matches first, then names starting with the search, then the
// biggest fires
const suggestions = computed(() => {
  const list = props.fireList;
  const search = filters.name.trim().toLowerCase();
  if (!list || search.length < 2) return [];
  const rank = (i) => (list.lowerNames[i] === search ? 2 : list.lowerNames[i].startsWith(search) ? 1 : 0);
  const matches = [];
  for (let i = 0; i < list.count; i++) {
    if (list.lowerNames[i].includes(search)) matches.push(i);
  }
  matches.sort((a, b) => rank(b) - rank(a) || (list.columns.size[b] ?? 0) - (list.columns.size[a] ?? 0));
  return matches.slice(0, MAX_SUGGESTIONS);
});

function describeFire(i) {
  const columns = props.fireList.columns;
  const states = (columns.states[i] ?? "")
    .split("|")
    .filter(Boolean)
    .map((code) => code.split("-").slice(1).join("-"))
    .join(", ");
  return [columns.year[i], states, formatArea(columns.size[i], settings.areaUnit)]
    .filter(Boolean)
    .join(" · ");
}

function pick(i) {
  emit("pick", props.fireList.columns.id[i]);
  searchOpen.value = false;
}

function onSearchKey(event) {
  const count = suggestions.value.length;
  if (event.key === "ArrowDown" && count) {
    searchOpen.value = true;
    activeSuggestion.value = (activeSuggestion.value + 1) % count;
  } else if (event.key === "ArrowUp" && count) {
    activeSuggestion.value = (activeSuggestion.value - 1 + count) % count;
  } else if (event.key === "Enter" && searchOpen.value && count) {
    pick(suggestions.value[Math.max(0, activeSuggestion.value)]);
  } else if (event.key === "Escape") {
    searchOpen.value = false;
    return;
  } else {
    return;
  }
  event.preventDefault();
}

// Typing reopens the suggestions, but not the name changing some other way
// (a link, Reset)
const searchInput = ref(null);
watch(() => filters.name, () => {
  searchOpen.value = document.activeElement === searchInput.value;
  activeSuggestion.value = -1;
});

// --- Decades: shortcuts for the year slider --------------------------------

const decades = computed(() => {
  if (!props.meta) return [];
  const list = [];
  for (let decade = MIN_YEAR; decade <= props.meta.max_year; decade += 10) list.push(decade);
  return list;
});
const decadeRange = (decade) => [decade, Math.min(decade + 9, props.meta.max_year)];
const isDecade = (decade) =>
  filters.years[0] === decade && filters.years[1] === decadeRange(decade)[1];

// Clicking the selected decade again goes back to all years
function toggleDecade(decade) {
  filters.years = isDecade(decade) ? [MIN_YEAR, props.meta.max_year] : decadeRange(decade);
}

const MONTHS = Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleString(undefined, { month: "short" }),
);

// Busiest first in the data, but alphabetical reads better in a checklist
const countries = computed(() =>
  [...(props.meta?.countries ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
);
const regionSearch = ref("");
const regions = computed(() => {
  const search = regionSearch.value.trim().toLowerCase();
  return [...(props.meta?.regions ?? [])]
    .filter((r) => !search || r.name.toLowerCase().includes(search) || filters.regions.includes(r.code))
    .sort((a, b) => a.name.localeCompare(b.name));
});
const showCountryNames = computed(() => countries.value.length > 1);

function formatSize(value) {
  if (value === Infinity) return "any";
  if (value === 0) return "0";
  const number = value.toLocaleString(undefined, { notation: "compact" });
  return `${number} ${AREA_UNITS[settings.areaUnit].symbol}`;
}
const sizeStops = computed(() => SIZE_STOPS[settings.areaUnit]);
const sizeLabel = (index) => formatSize(sizeStops.value[index]);
const durationLabel = (index) => DURATION_STOPS[index].label;

function rangeText(range, label, lastIndex) {
  const [min, max] = range;
  if (min === 0 && max === lastIndex) return "Any";
  if (min === 0) return `Up to ${label(max)}`;
  if (max === lastIndex) return `${label(min)} or more`;
  return `${label(min)} – ${label(max)}`;
}
</script>

<template>
  <div class="filters">
    <div class="filters-header">
      <h2>Filters</h2>
      <button
        type="button"
        class="clear-button"
        :disabled="activeFilterCount === 0"
        @click="resetFilters"
      >
        Clear filters<template v-if="activeFilterCount > 0"> ({{ activeFilterCount }})</template>
      </button>
    </div>

    <div class="search">
      <input
        ref="searchInput"
        v-model="filters.name"
        type="search"
        class="name-search"
        placeholder="Search fire names"
        aria-label="Search fire names"
        role="combobox"
        aria-autocomplete="list"
        aria-controls="fire-suggestions"
        :aria-expanded="searchOpen && suggestions.length > 0"
        :aria-activedescendant="activeSuggestion >= 0 ? `suggestion-${activeSuggestion}` : undefined"
        @focus="searchOpen = true"
        @blur="searchOpen = false"
        @keydown="onSearchKey"
      />
      <ul v-if="searchOpen && suggestions.length > 0" id="fire-suggestions" class="suggestions" role="listbox">
        <!-- mousedown, not click: click comes after the input's blur has closed the list -->
        <li
          v-for="(i, n) in suggestions"
          :id="`suggestion-${n}`"
          :key="i"
          role="option"
          :aria-selected="n === activeSuggestion"
          :class="{ active: n === activeSuggestion }"
          @mousedown.prevent="pick(i)"
        >
          <span class="suggestion-name">{{ toTitleCase(fireList.columns.fire_name[i]) || "Unnamed" }}</span>
          <span class="suggestion-detail">{{ describeFire(i) }}</span>
        </li>
      </ul>
    </div>

    <h3>Years</h3>
    <div v-if="meta" class="slider">
      <VueSlider v-model="filters.years" :contained="true" :min="MIN_YEAR" :max="meta.max_year" />
      <div class="range-text">{{ filters.years[0] }} – {{ filters.years[1] }}</div>
      <div class="decades">
        <button
          v-for="decade in decades"
          :key="decade"
          type="button"
          class="decade"
          :aria-pressed="isDecade(decade)"
          @click="toggleDecade(decade)"
        >
          {{ decade }}s
        </button>
      </div>
    </div>

    <ControlSection title="Location" :badge="activeFilters.location || null">
      <template v-if="showCountryNames">
        <h4>Country</h4>
        <label v-for="country in countries" :key="country.code" class="check">
          <input v-model="filters.countries" type="checkbox" :value="country.code" />
          {{ country.name }} <span class="count">{{ country.count.toLocaleString() }}</span>
        </label>
        <h4>State / province</h4>
      </template>
      <input
        v-if="(meta?.regions.length ?? 0) > 12"
        v-model="regionSearch"
        type="search"
        class="list-search"
        placeholder="Find a state"
        aria-label="Find a state or province"
      />
      <div class="scroll-list">
        <label v-for="region in regions" :key="region.code" class="check">
          <input v-model="filters.regions" type="checkbox" :value="region.code" />
          {{ region.name }}<template v-if="showCountryNames">, {{ region.country }}</template>
          <span class="count">{{ region.count.toLocaleString() }}</span>
        </label>
      </div>
    </ControlSection>

    <ControlSection title="Size" :badge="activeFilters.size">
      <div class="slider">
        <VueSlider
          v-model="filters.size"
          :min="0"
          :max="sizeStops.length - 1"
          :interval="1"
          :contained="true"
          :tooltip-formatter="sizeLabel"
          tooltip="focus"
        />
        <div class="range-text">{{ rangeText(filters.size, sizeLabel, sizeStops.length - 1) }}</div>
      </div>
    </ControlSection>

    <ControlSection title="Burn time" :badge="activeFilters.duration">
      <div class="slider">
        <VueSlider
          v-model="filters.duration"
          :min="0"
          :max="DURATION_STOPS.length - 1"
          :interval="1"
          :contained="true"
          :tooltip-formatter="durationLabel"
          tooltip="focus"
        />
        <div class="range-text">
          {{ rangeText(filters.duration, durationLabel, DURATION_STOPS.length - 1) }}
        </div>
      </div>
      <p class="note">
        From discovery to containment. Only fires with both dates recorded (mostly California and
        2020 on) match once this is set.
      </p>
    </ControlSection>

    <ControlSection title="Month started" :badge="activeFilters.months || null">
      <div class="months">
        <label v-for="(month, i) in MONTHS" :key="i" class="chip">
          <input v-model="filters.months" type="checkbox" :value="i + 1" />
          <span>{{ month }}</span>
        </label>
      </div>
      <p class="note">Only fires with a recorded start date (mostly California and 2020 on).</p>
    </ControlSection>

    <ControlSection title="Cause" :badge="activeFilters.causes || null">
      <label v-for="(name, code) in REASON_CODES" :key="code" class="check">
        <input v-model="filters.causes" type="checkbox" :value="Number(code)" />
        {{ name }}
      </label>
    </ControlSection>

    <ControlSection title="Fire type" :badge="activeFilters.kinds">
      <label v-for="(label, kind) in FIRE_KINDS" :key="kind" class="check">
        <input v-model="filters.kinds" type="checkbox" :value="kind" />
        {{ label }}
      </label>
    </ControlSection>

    <ControlSection title="Data source" :badge="activeFilters.sources">
      <label v-for="source in meta?.sources ?? []" :key="source.name" class="check">
        <input v-model="filters.sources" type="checkbox" :value="source.name" />
        {{ SOURCE_LABELS[source.name] ?? source.title }}
        <span class="count">{{ (source.kept ?? 0).toLocaleString() }}</span>
      </label>
    </ControlSection>
  </div>
</template>

<style scoped>
.filters-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

h2 {
  font-size: 1em;
  margin: 12px 0 8px;
}

h3 {
  font-size: 0.95em;
  margin: 12px 0 4px;
}

h4 {
  font-size: 0.9em;
  margin: 4px 0;
}

.clear-button {
  padding: 2px 10px;
  border: 1px solid #c62828;
  border-radius: 4px;
  background: #fff;
  color: #c62828;
  font: inherit;
  font-size: 0.85em;
  cursor: pointer;
}

.clear-button:hover:not(:disabled) {
  background: #c62828;
  color: #fff;
}

/* Always there so it's easy to find, but greyed out with nothing to clear */
.clear-button:disabled {
  border-color: #ccc;
  color: #aaa;
  cursor: default;
}

.name-search,
.list-search {
  width: 100%;
  box-sizing: border-box;
  padding: 5px 8px;
  border: 1px solid #bbb;
  border-radius: 4px;
  font: inherit;
}

.list-search {
  margin-bottom: 6px;
  font-size: 0.9em;
}

.slider {
  padding: 4px 8px 4px 0;
  margin-bottom: 8px;
}

.range-text {
  text-align: center;
  color: #555;
  margin-top: 4px;
  font-size: 0.9em;
}

.check {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}

.count {
  margin-left: auto;
  color: #888;
  font-size: 0.85em;
}

.scroll-list {
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Above the controls below it: the slider handles have their own z-index
   (5, from vue-slider-component), which would otherwise draw over the
   suggestions */
.search {
  position: relative;
  z-index: 10;
}

.suggestions {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  right: 0;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: #fff;
  border: 1px solid #bbb;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.suggestions li {
  display: flex;
  flex-direction: column;
  padding: 4px 8px;
  cursor: pointer;
}

.suggestions li.active,
.suggestions li:hover {
  background: #fff3c4;
}

.suggestion-detail {
  color: #777;
  font-size: 0.8em;
}

.decades {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  margin-top: 8px;
}

.decade {
  padding: 2px 0;
  border: 1px solid #bbb;
  border-radius: 4px;
  background: none;
  font: inherit;
  font-size: 0.8em;
  cursor: pointer;
}

.decade[aria-pressed="true"] {
  background: #c62828;
  border-color: #c62828;
  color: #fff;
}

.months {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
}

/* Checkboxes that look like toggle chips. The chip is the positioning parent
   for its hidden checkbox, otherwise the checkbox is placed relative to the
   page and focusing it scrolls the whole page instead of the sidebar. */
.chip {
  position: relative;
}

.chip input {
  position: absolute;
  opacity: 0;
}

.chip span {
  display: block;
  padding: 3px 0;
  border: 1px solid #bbb;
  border-radius: 4px;
  text-align: center;
  font-size: 0.85em;
  cursor: pointer;
  user-select: none;
}

.chip input:checked + span {
  background: #c62828;
  border-color: #c62828;
  color: #fff;
}

.chip input:focus-visible + span {
  outline: 2px solid #1565c0;
}

.note {
  margin: 6px 0 0;
  color: #777;
  font-size: 0.8em;
}
</style>

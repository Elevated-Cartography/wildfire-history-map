<script setup>
import {
  faMagnifyingGlassPlus,
  faSort,
  faSortDown,
  faSortUp,
} from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import {
  createSortedRowModel,
  rowSortingFeature,
  sortFn_text,
  tableFeatures,
  useTable,
} from "@tanstack/vue-table";
import { useVirtualizer } from "@tanstack/vue-virtual";
import { computed, nextTick, ref, watch } from "vue";
import { REASON_CODES, SOURCE_LABELS } from "../constants.js";
import { settings } from "../settings.js";
import { formatArea } from "../units.js";
import { formatFireDate, toTitleCase } from "../util.js";

const props = defineProps({
  // fires.json, see fireList.js
  fireList: { type: Object, required: true },
  // Indexes into fireList of the fires to show
  indices: { type: Array, required: true },
  hoveredId: { type: Number, default: null },
  focusedId: { type: Number, default: null },
  emptyMessage: { type: String, default: "No fires." },
});
// hover/focus/zoom: a fire's feature ID (hover can be null)
const emit = defineEmits(["hover", "focus", "zoom"]);

// Every row is one line high, so the virtualizer doesn't have to measure
const ROW_HEIGHT = 29;

// Rows are fire indexes; columns read from fires.json's arrays
const value = (name) => (i) => props.fireList.columns[name][i] ?? undefined;

// "|US-CA|US-NV|" -> "CA, NV"
function formatStates(states) {
  if (!states) return undefined;
  return states
    .split("|")
    .filter(Boolean)
    .map((code) => code.split("-").slice(1).join("-") || code)
    .join(", ");
}

function formatDuration(days) {
  if (days == null) return "";
  if (days < 1) return "< 1 day";
  const rounded = Math.round(days);
  return `${rounded.toLocaleString()} ${rounded === 1 ? "day" : "days"}`;
}

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: { text: sortFn_text },
});

// Numbers sort biggest/newest first on the first click, text A-Z. Widths are
// fixed so columns don't jump around as different rows scroll into view.
const columns = [
  { id: "year", header: "Year", width: 64, accessorFn: value("year"), sortDescFirst: true },
  { id: "name", header: "Name", width: 200, accessorFn: (i) => toTitleCase(value("fire_name")(i)) || undefined, sortFn: "text" },
  { id: "cause", header: "Cause", width: 170, accessorFn: (i) => REASON_CODES[value("cause")(i)], sortFn: "text" },
  { id: "size", header: "Size", width: 120, accessorFn: value("size"), sortDescFirst: true },
  { id: "duration", header: "Burn time", width: 115, accessorFn: value("duration_days"), sortDescFirst: true },
  { id: "states", header: "State", width: 80, accessorFn: (i) => formatStates(value("states")(i)), sortFn: "text" },
  { id: "agency", header: "Agency", width: 95, accessorFn: (i) => value("agency")(i) || undefined, sortFn: "text" },
  { id: "source", header: "Source", width: 105, accessorFn: (i) => SOURCE_LABELS[value("source")(i)], sortFn: "text" },
  { id: "comments", header: "Comments", accessorFn: (i) => value("comments")(i) || undefined, sortFn: "text" },
].map((column) => ({ sortUndefined: "last", ...column }));

const table = useTable({
  features,
  columns,
  data: computed(() => props.indices),
  getRowId: (i) => String(props.fireList.columns.id[i]),
  // Biggest first: the fires you've most likely heard of
  initialState: { sorting: [{ id: "size", desc: true }] },
});

const rows = computed(() => table.getRowModel().rows);


const scroller = ref(null);
const virtualizer = useVirtualizer(
  computed(() => ({
    count: rows.value.length,
    getScrollElement: () => scroller.value,
    estimateSize: () => ROW_HEIGHT,
    overscan: 15,
  })),
);
const virtualRows = computed(() => virtualizer.value.getVirtualItems());
// Empty rows above and below the rendered ones stand in for everything else
const paddingTop = computed(() => virtualRows.value[0]?.start ?? 0);
const paddingBottom = computed(
  () => virtualizer.value.getTotalSize() - (virtualRows.value.at(-1)?.end ?? 0),
);

function sortIcon(column) {
  const sorted = column.getIsSorted();
  return sorted === "asc" ? faSortUp : sorted === "desc" ? faSortDown : faSort;
}

function ariaSort(column) {
  const sorted = column.getIsSorted();
  return sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none";
}

function dateTooltip(i) {
  const discovered = formatFireDate(value("alarm_date")(i));
  const contained = formatFireDate(value("cont_date")(i));
  const lines = [];
  if (discovered) lines.push(`Discovered: ${discovered}`);
  if (contained) lines.push(`Contained: ${contained}`);
  return lines.join("\n") || null;
}

// When a fire gets focused from somewhere else (the map, search, a link),
// bring its row into view. A link's fire is focused before the list has any
// rows, so the scroll waits for the first non-empty rows after the focus
// change, then gives up if the fire isn't in them (filtered out, off screen).
let pendingScrollId = props.focusedId;

function scrollToPending() {
  if (pendingScrollId == null || rows.value.length === 0) return;
  const index = rows.value.findIndex((row) => row.id === String(pendingScrollId));
  if (index >= 0) {
    virtualizer.value.scrollToIndex(index, { align: "auto" });
  }
  pendingScrollId = null;
}

watch(
  () => props.focusedId,
  async (id) => {
    pendingScrollId = id;
    await nextTick();
    scrollToPending();
  },
);

watch(rows, async () => {
  await nextTick();
  scrollToPending();
});
</script>

<template>
  <div ref="scroller" class="scroller">
    <div v-if="indices.length === 0" class="empty">
      <p>{{ emptyMessage }}</p>
      <!-- e.g. a way out when the filters are too narrow -->
      <slot name="empty"></slot>
    </div>
    <table v-else class="results">
      <colgroup>
        <col style="width: 36px" />
        <col v-for="column in columns" :key="column.id" :style="column.width ? { width: `${column.width}px` } : {}" />
      </colgroup>
      <thead>
        <tr v-for="group in table.getHeaderGroups()" :key="group.id">
          <th class="col-zoom"><span class="visually-hidden">Zoom</span></th>
          <th
            v-for="header in group.headers"
            :key="header.id"
            :aria-sort="ariaSort(header.column)"
            :class="['col-' + header.column.id]"
          >
            <button
              type="button"
              class="sort-button"
              @click="header.column.getToggleSortingHandler()?.($event)"
            >
              {{ header.column.columnDef.header }}
              <FontAwesomeIcon :icon="sortIcon(header.column)" class="sort-icon" />
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="paddingTop > 0" aria-hidden="true">
          <td :colspan="columns.length + 1" :style="{ height: `${paddingTop}px`, padding: 0 }"></td>
        </tr>
        <tr
          v-for="virtualRow in virtualRows"
          :key="rows[virtualRow.index].id"
          :class="{
            odd: virtualRow.index % 2 === 0,
            focused: rows[virtualRow.index].id === String(focusedId),
            hovered: rows[virtualRow.index].id === String(hoveredId),
          }"
          @mouseenter="emit('hover', Number(rows[virtualRow.index].id))"
          @mouseleave="emit('hover', null)"
          @click="emit('focus', Number(rows[virtualRow.index].id))"
        >
          <td class="col-zoom">
            <button
              type="button"
              class="zoom-button"
              title="Zoom to this fire"
              @click.stop="emit('zoom', Number(rows[virtualRow.index].id))"
            >
              <FontAwesomeIcon :icon="faMagnifyingGlassPlus" />
            </button>
          </td>
          <td
            v-for="cell in rows[virtualRow.index].getAllCells()"
            :key="cell.id"
            :class="['col-' + cell.column.id]"
          >
            <template v-if="cell.column.id === 'year'">
              <span
                v-if="dateTooltip(rows[virtualRow.index].original)"
                class="has-tooltip"
                :title="dateTooltip(rows[virtualRow.index].original)"
                >{{ cell.getValue() }}</span
              >
              <template v-else>{{ cell.getValue() }}</template>
            </template>
            <template v-else-if="cell.column.id === 'size'">
              {{ formatArea(cell.getValue(), settings.areaUnit) }}
            </template>
            <template v-else-if="cell.column.id === 'duration'">
              {{ formatDuration(cell.getValue()) }}
            </template>
            <!-- Text can be cut off, so the full value is in a tooltip -->
            <span v-else :title="cell.getValue()">{{ cell.getValue() }}</span>
          </td>
        </tr>
        <tr v-if="paddingBottom > 0" aria-hidden="true">
          <td :colspan="columns.length + 1" :style="{ height: `${paddingBottom}px`, padding: 0 }"></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.scroller {
  height: 100%;
  overflow: auto;
}

.empty {
  margin: 12px;
  color: #666;
}

.empty p {
  margin: 0 0 8px;
}

.results {
  width: 100%;
  min-width: 1000px;
  table-layout: fixed;
  border-collapse: collapse;
}

th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #e8e8e8;
  text-align: left;
  white-space: nowrap;
  padding: 0;
}

.sort-button {
  width: 100%;
  padding: var(--padding-size) calc(var(--padding-size) * 2);
  background: none;
  border: none;
  font: inherit;
  font-weight: bold;
  text-align: left;
  cursor: pointer;
}

.sort-icon {
  margin-left: 4px;
  color: #999;
}

th[aria-sort="ascending"] .sort-icon,
th[aria-sort="descending"] .sort-icon {
  color: #000;
}

td {
  height: 29px;
  box-sizing: border-box;
  padding: 0 calc(var(--padding-size) * 2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

td.col-size,
td.col-duration {
  text-align: right;
}

td.col-zoom {
  padding: 0;
  text-align: center;
}

.zoom-button {
  width: 28px;
  height: 26px;
  padding: 0;
  border: none;
  background: none;
  color: #999;
  cursor: pointer;
}

.zoom-button:hover,
.zoom-button:focus-visible {
  color: #1565c0;
}

tbody tr {
  cursor: pointer;
}

tbody tr.odd {
  background-color: #ececec;
}

tbody tr.hovered {
  background-color: #fff3c4;
}

tbody tr.focused {
  background-color: #ffd27a;
}

.has-tooltip {
  text-decoration: underline dotted;
  cursor: help;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { SOURCE_LABELS } from "../constants.js";
import { formatArea } from "../units.js";
import { toTitleCase } from "../util.js";

// A menu for choosing between overlapping fires under a map click
const props = defineProps({
  // [{id, properties}], smallest first
  fires: { type: Array, required: true },
  // Where the click was, in pixels within the map
  x: { type: Number, required: true },
  y: { type: Number, required: true },
  areaUnit: { type: String, required: true },
});
// pick/hover: a fire's feature ID (hover can be null)
const emit = defineEmits(["pick", "hover", "close"]);

const MARGIN = 8;
const menu = ref(null);
const position = ref({ left: props.x, top: props.y });

function label(fire) {
  const p = fire.properties;
  return toTitleCase(p.fire_name) || "Unnamed";
}

function detail(fire) {
  const p = fire.properties;
  return [p.year, formatArea(p.size, props.areaUnit), SOURCE_LABELS[p.source] ?? p.source]
    .filter(Boolean)
    .join(" · ");
}

function pick(fire) {
  emit("pick", fire.id);
}

// Arrow keys move between items, Esc closes
function onKeyDown(event) {
  const items = [...menu.value.querySelectorAll("button")];
  const index = items.indexOf(document.activeElement);
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    const step = event.key === "ArrowDown" ? 1 : -1;
    items[(index + step + items.length) % items.length]?.focus();
    event.preventDefault();
  } else if (event.key === "Escape") {
    emit("close");
  }
}

// Clicking anywhere outside closes it (clicks on the map are handled by the
// map, which opens a new menu or picks a fire)
function onPointerDown(event) {
  if (!menu.value?.contains(event.target)) {
    emit("close");
  }
}

onMounted(async () => {
  await nextTick();
  // Keep it inside the map: open up/left of the click if there's no room
  const parent = menu.value.offsetParent.getBoundingClientRect();
  const { width, height } = menu.value.getBoundingClientRect();
  position.value = {
    left: props.x + width + MARGIN > parent.width ? Math.max(MARGIN, props.x - width) : props.x,
    top: props.y + height + MARGIN > parent.height ? Math.max(MARGIN, props.y - height) : props.y,
  };
  menu.value.querySelector("button")?.focus({ preventScroll: true });
  window.addEventListener("pointerdown", onPointerDown, true);
});

onBeforeUnmount(() => {
  window.removeEventListener("pointerdown", onPointerDown, true);
  emit("hover", null);
});
</script>

<template>
  <div
    ref="menu"
    class="fire-picker"
    role="menu"
    aria-label="Fires here"
    :style="{ left: `${position.left}px`, top: `${position.top}px` }"
    @keydown="onKeyDown"
  >
    <div class="title">{{ fires.length }} fires here</div>
    <button
      v-for="fire in fires"
      :key="fire.id"
      type="button"
      role="menuitem"
      @click="pick(fire)"
      @mouseenter="emit('hover', fire.id)"
      @focus="emit('hover', fire.id)"
      @mouseleave="emit('hover', null)"
    >
      <span class="name">{{ label(fire) }}</span>
      <span class="detail">{{ detail(fire) }}</span>
    </button>
  </div>
</template>

<style scoped>
.fire-picker {
  position: absolute;
  z-index: 3;
  min-width: 200px;
  max-width: 280px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px 0;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.title {
  padding: 4px 12px 6px;
  color: #777;
  font-size: 0.8em;
  border-bottom: 1px solid #eee;
}

button {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 5px 12px;
  border: none;
  background: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

button:hover,
button:focus-visible {
  background: #fff3c4;
  outline: none;
}

.name {
  font-weight: bold;
}

.detail {
  color: #777;
  font-size: 0.85em;
}
</style>

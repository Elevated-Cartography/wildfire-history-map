<script setup>
import { faChevronDown, faChevronUp } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { ref } from "vue";

defineProps({
  title: { type: String, required: true },
});
const collapsed = defineModel("collapsed", { type: Boolean, default: false });

const MIN_HEIGHT = 120;
const height = ref(Math.round(window.innerHeight * 0.35));

// Drag the top edge to resize
function startResize(event) {
  const startY = event.clientY;
  const startHeight = height.value;
  const onMove = (e) => {
    const maxHeight = window.innerHeight * 0.8;
    height.value = Math.min(maxHeight, Math.max(MIN_HEIGHT, startHeight + startY - e.clientY));
  };
  const onUp = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
  event.preventDefault();
}
</script>

<template>
  <section class="results-panel" :style="{ height: collapsed ? 'auto' : `${height}px` }">
    <div v-if="!collapsed" class="resize-handle" title="Drag to resize" @pointerdown="startResize"></div>
    <header>
      <button type="button" class="toggle" :aria-expanded="!collapsed" @click="collapsed = !collapsed">
        <FontAwesomeIcon :icon="collapsed ? faChevronUp : faChevronDown" />
        <h2>{{ title }}</h2>
      </button>
      <!-- Controls and a summary next to the title -->
      <slot name="header"></slot>
    </header>
    <div v-show="!collapsed" class="body">
      <slot></slot>
    </div>
  </section>
</template>

<style scoped>
.results-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  background: #f7f7f7;
  border-top: 1px solid #ccc;
  min-height: 0;
}

.resize-handle {
  position: absolute;
  top: -4px;
  left: 0;
  right: 0;
  height: 8px;
  cursor: ns-resize;
  z-index: 2;
}

header {
  flex: none;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 4px 12px;
  border-bottom: 1px solid #ddd;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 4px 0;
  font: inherit;
  cursor: pointer;
}

h2 {
  margin: 0;
  font-size: 1.1em;
}

.body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>

<script setup>
import { faCaretDown, faCaretRight } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { ref } from "vue";

defineProps({
  title: String,
  // Shown next to the title when set, e.g. how many options are picked
  badge: { type: [String, Number, Boolean], default: null },
});

const expanded = ref(false);
</script>

<template>
  <div class="control-section">
    <button type="button" class="header" :aria-expanded="expanded" @click="expanded = !expanded">
      <FontAwesomeIcon :icon="expanded ? faCaretDown : faCaretRight" class="caret" />
      <h4 class="control-title">{{ title }}</h4>
      <span v-if="badge" class="badge">{{ badge === true ? "on" : badge }}</span>
    </button>
    <div v-show="expanded" class="body">
      <slot></slot>
    </div>
  </div>
</template>

<style scoped>
.control-section {
  border-top: 1px solid #ddd;
}

.header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 0;
  background: none;
  border: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.caret {
  width: 10px;
}

.control-title {
  margin: 0;
  user-select: none;
}

.badge {
  margin-left: auto;
  padding: 0 7px;
  border-radius: 10px;
  background: #c62828;
  color: #fff;
  font-size: 0.8em;
  line-height: 1.6;
}

.body {
  padding: 0 0 10px 16px;
}
</style>

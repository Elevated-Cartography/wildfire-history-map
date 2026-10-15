<script setup>
import { BASEMAPS } from "../basemap.js";
import { settings } from "../settings.js";
import { TERRAIN_EXAGGERATIONS } from "../terrain.js";
import { AREA_UNITS, DISTANCE_UNITS } from "../units.js";
import AppDialog from "./AppDialog.vue";

const open = defineModel("open", { type: Boolean, default: false });
</script>

<template>
  <AppDialog v-model:open="open" title="Settings">
    <fieldset>
      <legend>Basemap</legend>
      <label v-for="(basemap, key) in BASEMAPS" :key="key" class="choice">
        <input v-model="settings.basemap" type="radio" name="basemap" :value="key" />
        {{ basemap.label }}
      </label>
    </fieldset>

    <fieldset>
      <legend>3D terrain</legend>
      <label class="choice">
        <input v-model="settings.terrain" type="checkbox" />
        Show terrain in 3D (also the mountain button on the map)
      </label>
      <label class="row">
        Exaggeration
        <select v-model.number="settings.terrainExaggeration">
          <option v-for="(label, value) in TERRAIN_EXAGGERATIONS" :key="value" :value="Number(value)">
            {{ label }}
          </option>
        </select>
      </label>
    </fieldset>

    <fieldset>
      <legend>Units</legend>
      <label class="row">
        Area
        <select v-model="settings.areaUnit">
          <option v-for="(unit, key) in AREA_UNITS" :key="key" :value="key">
            {{ unit.label }} ({{ unit.symbol }})
          </option>
        </select>
      </label>
      <label class="row">
        Distance
        <select v-model="settings.distanceUnit">
          <option v-for="(unit, key) in DISTANCE_UNITS" :key="key" :value="key">
            {{ unit.label }}
          </option>
        </select>
      </label>
    </fieldset>

    <p class="note">Settings are saved in this browser.</p>
  </AppDialog>
</template>

<style scoped>
fieldset {
  border: 1px solid #ccc;
  border-radius: 6px;
  margin: 0 0 16px;
  padding: 8px 12px 12px;
}

legend {
  font-weight: bold;
  padding: 0 4px;
}

.choice {
  display: block;
  padding: 3px 0;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
}

.note {
  margin: 0;
  color: #666;
  font-size: 0.9em;
}
</style>

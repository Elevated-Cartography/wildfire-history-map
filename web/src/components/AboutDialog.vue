<script setup>
import AppDialog from "./AppDialog.vue";

defineProps({
  // meta.json from `surtr build`, null until it loads
  meta: { type: Object, default: null },
});
const open = defineModel("open", { type: Boolean, default: false });

// Set by vite.config.js from the git remote, or null
const repoUrl = __REPO_URL__;

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "unknown";
}
</script>

<template>
  <AppDialog v-model:open="open" title="About">
    <p>
      An interactive map of historical wildfire perimeters in the United States and Canada, from
      public records kept by CAL FIRE, the National Interagency Fire Center and Natural Resources
      Canada. The list under the map
      shows the fires in view (or everywhere); click anywhere on the map to see just the fires
      that burned at that spot.
    </p>
    <p>
      These records are incomplete, especially for older fires: small fires often weren't
      mapped, and many early perimeters were lost or never digitized. Where a fire appears in
      more than one source, only one copy is shown.
    </p>

    <h3>Data sources</h3>
    <ul v-if="meta" class="sources">
      <li v-for="source in meta.sources" :key="source.name">
        <a :href="source.homepage" target="_blank" rel="noopener">{{ source.title }}</a>
        <div class="detail">
          {{ (source.kept ?? 0).toLocaleString() }} fires · updated
          {{ formatDate(source.last_edit) }}
        </div>
      </li>
    </ul>
    <p v-if="meta" class="detail">Map data built {{ formatDate(meta.generated_at) }}.</p>

    <h3>Credits</h3>
    <p class="detail">
      Basemap by <a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a>,
      © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a>,
      data from
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">
        OpenStreetMap</a>. Terrain from
      <a href="https://mapterhorn.com/" target="_blank" rel="noopener">Mapterhorn</a>.
      Canadian fire data contains information licensed under the
      <a href="https://open.canada.ca/en/open-government-licence-canada" target="_blank" rel="noopener">
        Open Government Licence – Canada</a>.
      Built with <a href="https://maplibre.org/" target="_blank" rel="noopener">MapLibre</a>,
      <a href="https://protomaps.com/docs/pmtiles" target="_blank" rel="noopener">PMTiles</a>
      and <a href="https://vuejs.org/" target="_blank" rel="noopener">Vue</a>.
      <template v-if="repoUrl">
        Source code on <a :href="repoUrl" target="_blank" rel="noopener">GitHub</a>.
      </template>
    </p>
  </AppDialog>
</template>

<style scoped>
h3 {
  margin: 20px 0 8px;
}

.sources {
  margin: 0;
  padding-left: 20px;
}

.sources li {
  margin-bottom: 8px;
}

.detail {
  color: #666;
  font-size: 0.9em;
}
</style>

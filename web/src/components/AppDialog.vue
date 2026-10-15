<script setup>
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { onMounted, ref, watch } from "vue";

defineProps({
  title: { type: String, required: true },
});
const open = defineModel("open", { type: Boolean, default: false });

// A native <dialog> gets focus trapping, Esc to close and a backdrop for free
const dialog = ref(null);

function sync(isOpen) {
  if (isOpen && !dialog.value.open) {
    dialog.value.showModal();
  } else if (!isOpen && dialog.value.open) {
    dialog.value.close();
  }
}

onMounted(() => sync(open.value));
watch(open, sync);
</script>

<template>
  <!-- Clicks on the backdrop land on the <dialog> itself, everything inside is in .content -->
  <dialog ref="dialog" class="app-dialog" @close="open = false" @click.self="open = false">
    <div class="content">
      <header>
        <h2>{{ title }}</h2>
        <button type="button" class="icon-button" aria-label="Close" @click="open = false">
          <FontAwesomeIcon :icon="faXmark" />
        </button>
      </header>
      <slot></slot>
    </div>
  </dialog>
</template>

<style scoped>
.app-dialog {
  padding: 0;
  border: none;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  width: min(560px, calc(100vw - 32px));
  max-height: calc(100vh - 64px);
}

.app-dialog::backdrop {
  background: rgba(0, 0, 0, 0.4);
}

.content {
  padding: 20px 24px 24px;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

h2 {
  margin: 0;
}
</style>

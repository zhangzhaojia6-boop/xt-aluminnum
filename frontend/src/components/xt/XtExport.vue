<template>
  <div class="xt-export">
    <button v-if="formats.length <= 1" type="button" class="xt-export__button" :disabled="disabled" @click="exportFormat(formats[0]?.value || 'xlsx')">
      {{ label }}
    </button>
    <div v-else class="xt-export__dropdown">
      <button type="button" class="xt-export__button" :disabled="disabled" @click="open = !open">
        {{ label }}
      </button>
      <div v-if="open" class="xt-export__menu">
        <button v-for="format in formats" :key="format.value" type="button" class="xt-export__item" @click="exportFormat(format.value)">
          {{ format.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineOptions({ name: 'XtExport' })

defineProps({
  label: {
    type: String,
    default: '导出'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  formats: {
    type: Array,
    default: () => [
      { label: 'Excel', value: 'xlsx' },
      { label: 'CSV', value: 'csv' }
    ]
  }
})

const emit = defineEmits(['export'])
const open = ref(false)

function exportFormat(format) {
  open.value = false
  emit('export', format)
}
</script>

<style scoped>
.xt-export {
  position: relative;
  display: inline-block;
}

.xt-export__dropdown {
  position: relative;
}

.xt-export__button,
.xt-export__item {
  height: 34px;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text);
  background: var(--xt-bg-panel);
}

.xt-export__button {
  padding: 0 var(--xt-space-4);
}

.xt-export__button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.xt-export__menu {
  position: absolute;
  top: calc(100% + var(--xt-space-1));
  right: 0;
  z-index: 100;
  min-width: 120px;
  padding: var(--xt-space-1);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-lg);
}

.xt-export__item {
  display: block;
  width: 100%;
  padding: 0 var(--xt-space-3);
  border: 0;
  text-align: left;
}

.xt-export__item:hover {
  background: var(--xt-gray-50);
}
</style>

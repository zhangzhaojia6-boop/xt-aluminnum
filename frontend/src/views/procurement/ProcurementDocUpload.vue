<template>
  <label class="pc-upload" :class="{ 'is-busy': busy }">
    <span>{{ label }}</span>
    <input
      type="file"
      accept="application/pdf,image/jpeg,image/png,image/webp"
      :capture="capture ? 'environment' : undefined"
      :disabled="busy"
      @change="onChange"
    />
  </label>
</template>

<script setup>
const props = defineProps({
  label: { type: String, required: true },
  docType: { type: String, required: true },
  busy: { type: Boolean, default: false },
  capture: { type: Boolean, default: false },
})
const emit = defineEmits(['pick'])

function onChange(event) {
  const file = event.target.files?.[0]
  if (file) emit('pick', props.docType, file)
  event.target.value = ''
}
</script>

<style scoped>
.pc-upload { position: relative; display: flex; align-items: center; justify-content: center; min-height: 52px; border: 1px dashed var(--xt-primary-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-primary); cursor: pointer; }
.pc-upload input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.pc-upload.is-busy { opacity: 0.6; }
.pc-upload:focus-within { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
</style>

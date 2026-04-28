<template>
  <form class="xt-filter" @submit.prevent="submit">
    <div class="xt-filter__fields">
      <label v-for="field in fields" :key="field.key" class="xt-filter__field">
        <span class="xt-filter__label">{{ field.label }}</span>
        <select
          v-if="field.type === 'select'"
          class="xt-filter__control"
          :value="localValue[field.key] ?? ''"
          @change="updateField(field.key, $event.target.value)"
        >
          <option value="">{{ field.placeholder || '全部' }}</option>
          <option v-for="option in field.options || []" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <input
          v-else
          class="xt-filter__control"
          :type="field.type || 'text'"
          :value="localValue[field.key] ?? ''"
          :placeholder="field.placeholder || '请输入'"
          @input="updateField(field.key, $event.target.value)"
        />
      </label>
    </div>
    <div class="xt-filter__actions">
      <button type="button" class="xt-filter__button" @click="reset">{{ resetText }}</button>
      <button type="submit" class="xt-filter__button xt-filter__button--primary">{{ submitText }}</button>
    </div>
  </form>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtFilter' })

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  },
  fields: {
    type: Array,
    default: () => []
  },
  submitText: {
    type: String,
    default: '筛选'
  },
  resetText: {
    type: String,
    default: '重置'
  }
})

const emit = defineEmits(['update:modelValue', 'submit', 'reset'])
const localValue = computed(() => props.modelValue || {})

function updateField(key, value) {
  emit('update:modelValue', { ...localValue.value, [key]: value })
}

function submit() {
  emit('submit', localValue.value)
}

function reset() {
  const nextValue = {}
  props.fields.forEach(field => {
    nextValue[field.key] = ''
  })
  emit('update:modelValue', nextValue)
  emit('reset', nextValue)
}
</script>

<style scoped>
.xt-filter {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-filter__fields {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--xt-space-3);
}

.xt-filter__field {
  display: grid;
  gap: var(--xt-space-1);
}

.xt-filter__label {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.xt-filter__control {
  width: 100%;
  height: 34px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text);
  background: var(--xt-bg-panel);
  outline: none;
  transition:
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease);
}

.xt-filter__control:focus {
  border-color: var(--xt-primary);
  box-shadow: 0 0 0 3px var(--xt-primary-light);
}

.xt-filter__actions {
  display: flex;
  flex: 0 0 auto;
  gap: var(--xt-space-2);
}

.xt-filter__button {
  height: 34px;
  padding: 0 var(--xt-space-4);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text);
  background: var(--xt-bg-panel);
}

.xt-filter__button--primary {
  border-color: var(--xt-primary);
  color: var(--xt-text-inverse);
  background: var(--xt-primary);
}

@media (max-width: 768px) {
  .xt-filter {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>

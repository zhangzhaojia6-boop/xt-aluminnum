<template>
  <section class="xt-table">
    <header v-if="title || $slots.actions" class="xt-table__header">
      <h2 v-if="title" class="xt-table__title">{{ title }}</h2>
      <div v-if="$slots.actions" class="xt-table__actions">
        <slot name="actions" />
      </div>
    </header>
    <div v-if="loading" class="xt-table__state">
      <XtSkeleton :rows="4" />
    </div>
    <XtEmpty v-else-if="!rows.length" :text="emptyText" />
    <div v-else class="xt-table__scroll" :style="scrollStyle">
      <table>
        <thead>
          <tr>
            <th v-if="selectable" class="xt-table__select">
              <input type="checkbox" :checked="allSelected" @change="toggleAll" />
            </th>
            <th v-for="column in columns" :key="column.key" :style="columnStyle(column)">
              {{ column.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="resolveKey(row, index)" @click="$emit('row-click', row)">
            <td v-if="selectable" class="xt-table__select" @click.stop>
              <input type="checkbox" :checked="isSelected(row)" @change="toggleRow(row)" />
            </td>
            <td v-for="column in columns" :key="column.key" :class="column.class">
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]" :column="column">
                {{ row[column.key] }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import XtEmpty from './XtEmpty.vue'
import XtSkeleton from './XtSkeleton.vue'

defineOptions({ name: 'XtTable' })

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  columns: {
    type: Array,
    default: () => []
  },
  rows: {
    type: Array,
    default: () => []
  },
  rowKey: {
    type: String,
    default: 'id'
  },
  loading: {
    type: Boolean,
    default: false
  },
  selectable: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  },
  maxHeight: {
    type: [String, Number],
    default: ''
  }
})

const emit = defineEmits(['row-click', 'selection-change'])
const selectedKeys = ref(new Set())

const scrollStyle = computed(() => {
  if (!props.maxHeight) return undefined
  return { maxHeight: typeof props.maxHeight === 'number' ? `${props.maxHeight}px` : props.maxHeight }
})

const allSelected = computed(() => props.rows.length > 0 && props.rows.every(row => selectedKeys.value.has(resolveKey(row))))

watch(() => props.rows, () => {
  const rowKeys = new Set(props.rows.map(row => resolveKey(row)))
  selectedKeys.value = new Set([...selectedKeys.value].filter(key => rowKeys.has(key)))
  emitSelection()
})

function resolveKey(row, index = 0) {
  return row?.[props.rowKey] ?? index
}

function columnStyle(column) {
  return column.width ? { width: typeof column.width === 'number' ? `${column.width}px` : column.width } : undefined
}

function isSelected(row) {
  return selectedKeys.value.has(resolveKey(row))
}

function toggleRow(row) {
  const next = new Set(selectedKeys.value)
  const key = resolveKey(row)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selectedKeys.value = next
  emitSelection()
}

function toggleAll(event) {
  selectedKeys.value = event.target.checked ? new Set(props.rows.map(row => resolveKey(row))) : new Set()
  emitSelection()
}

function emitSelection() {
  emit('selection-change', props.rows.filter(row => selectedKeys.value.has(resolveKey(row))))
}
</script>

<style scoped>
.xt-table {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-table::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  box-shadow: var(--xt-shadow-inset-hairline);
}

.xt-table__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4) var(--xt-space-5);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-table__title {
  margin: 0;
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-lg);
  font-weight: 850;
}

.xt-table__actions {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-table__state {
  padding: var(--xt-space-5);
}

.xt-table__scroll {
  overflow: auto;
}

.xt-table table {
  width: 100%;
  border-collapse: collapse;
}

.xt-table th,
.xt-table td {
  padding: var(--xt-space-3) var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
  text-align: left;
  vertical-align: middle;
}

.xt-table th {
  color: var(--xt-text-secondary);
  background: var(--xt-bg-panel-soft);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  letter-spacing: 0;
  white-space: nowrap;
}

.xt-table td {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}

.xt-table tbody tr {
  transition: background-color var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .xt-table tbody tr:hover {
    background: var(--xt-primary-light);
  }
}

.xt-table tbody tr:last-child td {
  border-bottom: 0;
}

.xt-table__select {
  width: 40px;
}
</style>

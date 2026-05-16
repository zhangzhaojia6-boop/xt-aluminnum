<template>
  <div class="xt-data-table" :class="{ 'xt-data-table--striped': striped, 'xt-data-table--compact': compact }">
    <div v-if="$slots.toolbar" class="xt-data-table__toolbar">
      <slot name="toolbar" />
    </div>
    <div class="xt-data-table__scroll">
      <table class="xt-data-table__table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :style="{ width: col.width, textAlign: col.align || 'left' }"
              class="xt-data-table__th"
            >
              {{ col.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in data" :key="rowKey ? row[rowKey] : idx" class="xt-data-table__row">
            <td
              v-for="col in columns"
              :key="col.key"
              :style="{ textAlign: col.align || 'left' }"
              class="xt-data-table__td"
              :data-source="col.source || ''"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>
          </tr>
          <tr v-if="!data.length" class="xt-data-table__empty">
            <td :colspan="columns.length">
              <slot name="empty">
                <span class="xt-data-table__empty-text">暂无数据</span>
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtDataTable' })

defineProps({
  columns: {
    type: Array,
    required: true
  },
  data: {
    type: Array,
    default: () => []
  },
  rowKey: {
    type: String,
    default: 'id'
  },
  striped: {
    type: Boolean,
    default: true
  },
  compact: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.xt-data-table {
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  overflow: hidden;
}

.xt-data-table__toolbar {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-data-table__scroll {
  overflow-x: auto;
}

.xt-data-table__table {
  width: 100%;
  border-collapse: collapse;
}

.xt-data-table__th {
  padding: var(--xt-space-3) var(--xt-space-4);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--xt-border-light);
  white-space: nowrap;
}

.xt-data-table__td {
  padding: var(--xt-space-3) var(--xt-space-4);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-data-table--compact .xt-data-table__th,
.xt-data-table--compact .xt-data-table__td {
  padding: var(--xt-space-2) var(--xt-space-3);
}

.xt-data-table--striped .xt-data-table__row:nth-child(even) {
  background: var(--xt-bg-subtle);
}

.xt-data-table__row:hover {
  background: var(--xt-bg-hover);
}

.xt-data-table__empty-text {
  display: block;
  padding: var(--xt-space-6) 0;
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
</style>

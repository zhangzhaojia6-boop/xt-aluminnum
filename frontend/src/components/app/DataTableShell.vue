<template>
  <section class="data-table-shell">
    <header v-if="title || subtitle || $slots.actions" class="data-table-shell__head">
      <div>
        <h2 v-if="title" class="data-table-shell__title">{{ title }}</h2>
        <p v-if="subtitle" class="data-table-shell__subtitle">{{ subtitle }}</p>
      </div>
      <div class="data-table-shell__actions">
        <slot name="actions" />
      </div>
    </header>
    <div v-if="loading" class="data-table-shell__state">正在加载…</div>
    <div v-else-if="rows.length === 0" class="data-table-shell__state">{{ emptyText }}</div>
    <div v-else class="data-table-shell__scroll">
      <table>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key">{{ column.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="row.id || index">
          <td v-for="column in columns" :key="column.key">
            <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
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
defineProps({
  title: {
    type: String,
    default: ''
  },
  subtitle: {
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
  loading: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  }
})
</script>

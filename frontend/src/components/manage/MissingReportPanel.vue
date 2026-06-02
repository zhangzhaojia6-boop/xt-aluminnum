<template>
  <section
    class="xt-missing-report"
    :class="{ 'xt-missing-report--compact': compact }"
    data-testid="missing-report-panel"
  >
    <header class="xt-missing-report__head">
      <div>
        <span>缺报追踪</span>
        <h2>{{ title }}</h2>
      </div>
      <strong>{{ summary.total }}</strong>
    </header>
    <div class="xt-missing-report__stats">
      <b>{{ summary.workshopCount }} 车间</b>
      <b>{{ summary.shiftCount }} 班次</b>
      <b>{{ summary.roleCount }} 岗位</b>
    </div>
    <div class="xt-missing-report__table">
      <table>
        <thead>
          <tr>
            <th>车间</th>
            <th>机列</th>
            <th>班次</th>
            <th>责任岗位</th>
            <th>责任人</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6">加载中...</td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td colspan="6">暂无缺报</td>
          </tr>
          <template v-else>
            <tr v-for="row in rows" :key="row.key">
              <td>{{ row.workshopName }}</td>
              <td><strong>{{ row.machineName }}</strong></td>
              <td>{{ row.shiftName }}</td>
              <td>{{ row.roleLabel }}</td>
              <td>{{ row.ownerName }}</td>
              <td><span>{{ row.statusText }}</span></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { summarizeMissingReportRows } from '../../utils/missingReportRows.js'

const props = defineProps({
  title: { type: String, default: '缺报明细' },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const summary = computed(() => summarizeMissingReportRows(props.rows))
</script>

<style scoped>
.xt-missing-report {
  position: relative;
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--xt-danger, #ff5d73) 24%, var(--xt-border-ink, rgba(125, 211, 252, 0.2)));
  border-radius: var(--xt-radius-xl, 18px);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--xt-danger, #ff5d73) 12%, transparent), transparent 48%),
    color-mix(in srgb, var(--xt-bg-ink-panel, #071b31) 86%, transparent);
  color: var(--xt-text-inverse, #e5f7ff);
  overflow: hidden;
}

.xt-missing-report::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(90deg, transparent, rgba(255, 93, 115, 0.12), transparent);
  transform: translateX(-100%);
  animation: xtMissingSweep 7s ease-in-out infinite;
}

.xt-missing-report__head,
.xt-missing-report__stats,
.xt-missing-report__table {
  position: relative;
  z-index: 1;
}

.xt-missing-report__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.xt-missing-report__head span {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 62%, transparent);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.xt-missing-report__head h2 {
  margin: 2px 0 0;
  font-size: 16px;
}

.xt-missing-report__head strong {
  color: var(--xt-danger, #ff5d73);
  font-family: var(--xt-font-display, inherit);
  font-size: 24px;
}

.xt-missing-report__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.xt-missing-report__stats b {
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 76%, transparent);
  font-size: 12px;
}

.xt-missing-report__table {
  overflow-x: auto;
  max-height: 220px;
  overflow-y: auto;
}

.xt-missing-report table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
}

.xt-missing-report th,
.xt-missing-report td {
  padding: 7px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
  white-space: nowrap;
}

.xt-missing-report th {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 58%, transparent);
  font-size: 12px;
}

.xt-missing-report td {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 84%, transparent);
  font-size: 12px;
}

.xt-missing-report td span {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--xt-danger, #ff5d73) 16%, transparent);
  color: var(--xt-danger, #ff5d73);
  font-weight: 800;
}

.xt-missing-report--compact {
  gap: 3px;
  padding: 6px 8px;
  border-radius: var(--xt-radius-md, 12px);
}

.xt-missing-report--compact .xt-missing-report__head h2 {
  margin-top: 0;
  font-size: 12px;
}

.xt-missing-report--compact .xt-missing-report__head strong {
  font-size: 16px;
}

.xt-missing-report--compact .xt-missing-report__head span {
  font-size: 10px;
}

.xt-missing-report--compact .xt-missing-report__stats b {
  padding: 1px 5px;
  font-size: 10px;
}

.xt-missing-report--compact .xt-missing-report__table {
  max-height: 72px;
}

.xt-missing-report--compact th,
.xt-missing-report--compact td {
  padding: 3px 5px;
  font-size: 10px;
}

.xt-missing-report--compact td span {
  padding: 2px 6px;
}

@keyframes xtMissingSweep {
  0% { transform: translateX(-100%); }
  55% { transform: translateX(100%); }
  100% { transform: translateX(100%); }
}
</style>

<template>
  <section class="pc-board" data-testid="procurement-board">
    <h1>采购总览</h1>
    <p v-if="loading" role="status">加载中</p>
    <p v-else-if="failed">读取失败 <button type="button" class="pc-board__retry" @click="load">重试</button></p>

    <template v-else>
      <ul class="pc-board__metrics">
        <li><RouterLink to="/procurement/ledger?status=open"><XtMetric label="在办" :value="String(board.open_count)" size="lg" /></RouterLink></li>
        <li><RouterLink to="/procurement/ledger?overdue=true"><XtMetric label="超时" :value="String(board.overdue_count)" size="lg" /></RouterLink></li>
        <li><RouterLink to="/procurement/ledger?emergency=true"><XtMetric label="紧急采购" :value="String(board.emergency_count)" size="lg" /></RouterLink></li>
        <li><XtMetric label="本月已付款" :value="board.month_paid_amount" unit="元" size="lg" /></li>
      </ul>

      <section v-if="board.emergency_backfill_overdue" class="pc-board__alert" data-testid="procurement-backfill">
        <RouterLink to="/procurement/ledger?emergency=true">紧急采购超期未补手续 {{ board.emergency_backfill_overdue }} 张</RouterLink>
      </section>

      <div class="pc-board__columns">
        <section>
          <h2>各环节在办</h2>
          <ol class="pc-bars" data-testid="procurement-funnel">
            <li v-for="row in board.funnel" :key="row.number">
              <span>{{ row.number }}. {{ row.label }}</span>
              <i><b :style="{ width: `${ratio(row.count, board.funnel, 'count')}%` }" /></i>
              <em>{{ row.count }}</em>
            </li>
          </ol>
        </section>

        <section>
          <h2>各环节平均耗时</h2>
          <ol v-if="board.step_hours.length" class="pc-bars" data-testid="procurement-hours">
            <li v-for="row in board.step_hours" :key="row.step">
              <span>{{ row.label }}</span>
              <i><b class="is-soft" :style="{ width: `${ratio(row.hours, board.step_hours, 'hours')}%` }" /></i>
              <em>{{ row.hours }}h</em>
            </li>
          </ol>
          <p v-else class="pc-board__empty">暂无</p>
        </section>

        <section>
          <h2>本月申请金额</h2>
          <ol v-if="board.month_by_category.length" class="pc-bars pc-bars--money">
            <li v-for="row in board.month_by_category" :key="row.category">
              <span>{{ row.category }}</span>
              <i><b :style="{ width: `${ratio(row.amount, board.month_by_category, 'amount')}%` }" /></i>
              <em>{{ formatMoney(row.amount) }}</em>
            </li>
          </ol>
          <p v-else class="pc-board__empty">暂无</p>
        </section>

        <section>
          <h2>供应商金额前 10</h2>
          <ol v-if="board.top_suppliers.length" class="pc-bars pc-bars--money">
            <li v-for="row in board.top_suppliers" :key="row.supplier">
              <span>{{ row.supplier }}</span>
              <i><b :style="{ width: `${ratio(row.amount, board.top_suppliers, 'amount')}%` }" /></i>
              <em>{{ formatMoney(row.amount) }}</em>
            </li>
          </ol>
          <p v-else class="pc-board__empty">暂无</p>
        </section>
      </div>

      <section v-if="board.split_warnings.length" data-testid="procurement-split">
        <h2>疑似拆单</h2>
        <ul class="pc-board__list">
          <li v-for="warning in board.split_warnings" :key="warning.request_nos.join()">
            <strong>{{ warning.material_name }} · {{ warning.supplier }}</strong>
            <span>合计 ¥{{ formatMoney(warning.total_amount) }}（{{ warning.request_nos.join('、') }}）</span>
          </li>
        </ul>
      </section>

      <section v-if="board.overdue.length">
        <h2>已超时</h2>
        <ul class="pc-board__list">
          <li v-for="row in board.overdue" :key="row.id">
            <RouterLink :to="`/procurement/${row.id}`">{{ row.request_no }} {{ row.material_name }}</RouterLink>
            <span>{{ row.step_label }}</span>
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { fetchProcurementBoard, formatMoney } from '../../api/procurement.js'
import XtMetric from '../../components/xt/XtMetric.vue'

const board = ref({})
const loading = ref(true)
const failed = ref(false)

function ratio(value, rows, key) {
  const top = Math.max(...rows.map((row) => Number(row[key])), 0)
  return top > 0 ? (Number(value) / top) * 100 : 0
}

async function load() {
  loading.value = true
  failed.value = false
  try {
    board.value = await fetchProcurementBoard()
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pc-board { display: grid; grid-template-columns: minmax(0, 1fr); gap: 40px; }
.pc-board h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-board h2 { margin: 0 0 16px; font-size: 20px; font-weight: 600; }
.pc-board__retry { min-height: 44px; padding: 0 16px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); font: inherit; cursor: pointer; }
.pc-board__metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 2fr); gap: 24px; margin: 0; padding: 0; list-style: none; }
.pc-board__metrics a { display: block; color: inherit; text-decoration: none; }
.pc-board__alert a { display: block; padding: 14px 16px; border-radius: 4px; background: var(--xt-danger-light, var(--xt-bg-panel-soft)); color: var(--xt-danger); font-weight: 600; text-decoration: none; }
.pc-board__columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 40px 64px; }
.pc-board__empty { margin: 0; color: var(--xt-text-muted); }
.pc-bars { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.pc-bars li { display: grid; grid-template-columns: 128px minmax(0, 1fr) 40px; align-items: center; gap: 12px; color: var(--xt-text-secondary); }
.pc-bars--money li { grid-template-columns: 128px minmax(0, 1fr) 96px; }
.pc-bars i { display: block; height: 12px; border-radius: 2px; background: var(--xt-bg-panel-soft); }
.pc-bars b { display: block; height: 100%; border-radius: 2px; background: var(--xt-primary); transform-origin: left; animation: pc-grow 700ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
.pc-bars b.is-soft { background: var(--xt-warning); }
.pc-bars em { color: var(--xt-text); font-style: normal; font-variant-numeric: tabular-nums; text-align: right; }
.pc-board__list { margin: 0; padding: 0; list-style: none; }
.pc-board__list li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; padding: 12px 0; border-bottom: 1px solid var(--xt-border); }
.pc-board__list strong { font-weight: 600; }
.pc-board__list span { color: var(--xt-text-secondary); }
.pc-board__list a { color: var(--xt-primary); text-decoration: none; }
@keyframes pc-grow { from { transform: scaleX(0); } }
@media (max-width: 800px) {
  .pc-board__metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pc-board__metrics li:last-child { grid-column: 1 / -1; }
  .pc-board__columns { grid-template-columns: minmax(0, 1fr); }
  .pc-bars li { grid-template-columns: 112px minmax(0, 1fr) 36px; }
  .pc-bars--money li { grid-template-columns: 96px minmax(0, 1fr) 84px; }
}
@media (prefers-reduced-motion: reduce) {
  .pc-bars b { animation: none; }
}
</style>

<template>
  <section class="pc-board" data-testid="procurement-board">
    <h1>采购台账</h1>
    <p v-if="loading" role="status">加载中</p>
    <p v-else-if="failed">读取失败 <button type="button" @click="load">重试</button></p>

    <template v-else>
      <ul class="pc-board__metrics">
        <li><XtMetric label="在办" :value="String(board.open_count)" size="lg" /></li>
        <li><XtMetric label="超时" :value="String(board.overdue_count)" size="lg" /></li>
        <li><XtMetric label="紧急采购" :value="String(board.emergency_count)" size="lg" /></li>
        <li><XtMetric label="本月已付款" :value="board.month_paid_amount" unit="元" size="lg" /></li>
      </ul>

      <section class="pc-board__block">
        <h2>各环节在办</h2>
        <ol class="pc-funnel" data-testid="procurement-funnel">
          <li v-for="row in board.funnel" :key="row.number">
            <span>{{ row.number }}. {{ row.label }}</span>
            <i><b :style="{ width: `${barWidth(row.count)}%` }" /></i>
            <em>{{ row.count }}</em>
          </li>
        </ol>
      </section>

      <section v-if="board.split_warnings.length" class="pc-board__block" data-testid="procurement-split">
        <h2>疑似拆单</h2>
        <ul class="pc-board__list">
          <li v-for="warning in board.split_warnings" :key="warning.request_nos.join()">
            <strong>{{ warning.material_name }} · {{ warning.supplier }}</strong>
            <span>合计 ¥{{ warning.total_amount }}（{{ warning.request_nos.join('、') }}）</span>
          </li>
        </ul>
      </section>

      <section v-if="board.overdue.length" class="pc-board__block">
        <h2>已超时</h2>
        <ul class="pc-board__list">
          <li v-for="row in board.overdue" :key="row.id">
            <RouterLink :to="`/procurement/${row.id}`">{{ row.request_no }} {{ row.material_name }}</RouterLink>
            <span>{{ row.step_label }}</span>
          </li>
        </ul>
      </section>

      <section class="pc-board__block">
        <h2>全部单据</h2>
        <div class="pc-board__table">
          <table data-testid="procurement-ledger">
            <thead>
              <tr><th>单号</th><th>物料</th><th>供应商</th><th class="is-num">金额</th><th>环节</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.id">
                <td><RouterLink :to="`/procurement/${row.id}`">{{ row.request_no }}</RouterLink></td>
                <td>{{ row.material_name }}</td>
                <td>{{ row.supplier || '-' }}</td>
                <td class="is-num">{{ row.amount }}</td>
                <td>{{ STATUS_LABELS[row.status] || row.step_label }}<small v-if="row.is_emergency"> 紧急</small></td>
              </tr>
              <tr v-if="!rows.length"><td colspan="5" class="is-empty">暂无单据</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <ProcurementAssignments v-if="meta.can_manage" :roles="meta.assignable_roles" />
    </template>
  </section>
</template>

<script setup>
import { inject, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { fetchProcurementBoard, fetchProcurementRequests } from '../../api/procurement.js'
import XtMetric from '../../components/xt/XtMetric.vue'
import ProcurementAssignments from './ProcurementAssignments.vue'

const meta = inject('procurementMeta')
const STATUS_LABELS = { archived: '已归档', closed_stock: '库存充足', cancelled: '已撤销' }
const board = ref({})
const rows = ref([])
const loading = ref(true)
const failed = ref(false)

function barWidth(count) {
  const top = Math.max(...board.value.funnel.map((row) => row.count), 1)
  return (count / top) * 100
}

async function load() {
  loading.value = true
  failed.value = false
  try {
    const [nextBoard, nextRows] = await Promise.all([fetchProcurementBoard(), fetchProcurementRequests('all')])
    board.value = nextBoard
    rows.value = nextRows
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
.pc-board__metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 2fr); gap: 24px; margin: 0; padding: 0; list-style: none; }
.pc-funnel { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.pc-funnel li { display: grid; grid-template-columns: 128px minmax(0, 1fr) 32px; align-items: center; gap: 12px; color: var(--xt-text-secondary); }
.pc-funnel i { display: block; height: 12px; border-radius: 2px; background: var(--xt-bg-panel-soft); }
.pc-funnel b { display: block; height: 100%; border-radius: 2px; background: var(--xt-primary); transform-origin: left; animation: pc-grow 700ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
.pc-funnel em { color: var(--xt-text); font-style: normal; font-variant-numeric: tabular-nums; text-align: right; }
.pc-board__list { margin: 0; padding: 0; list-style: none; }
.pc-board__list li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; padding: 12px 0; border-bottom: 1px solid var(--xt-border); }
.pc-board__list strong { font-weight: 600; }
.pc-board__list span { color: var(--xt-text-secondary); }
.pc-board a { color: var(--xt-primary); text-decoration: none; }
.pc-board__table { overflow-x: auto; }
.pc-board table { width: 100%; min-width: 560px; border-collapse: collapse; }
.pc-board th { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--xt-border); color: var(--xt-text-muted); font-size: 12px; font-weight: 400; text-align: left; }
.pc-board td { padding: 12px 12px 12px 0; border-bottom: 1px solid var(--xt-border); }
.pc-board .is-num { font-variant-numeric: tabular-nums; text-align: right; }
.pc-board small { color: var(--xt-warning); }
.pc-board .is-empty { padding: 32px 0; color: var(--xt-text-muted); text-align: center; }
@keyframes pc-grow { from { transform: scaleX(0); } }
@media (max-width: 700px) {
  .pc-board__metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pc-board__metrics li:last-child { grid-column: 1 / -1; }
  .pc-funnel li { grid-template-columns: 112px minmax(0, 1fr) 24px; }
}
@media (prefers-reduced-motion: reduce) {
  .pc-funnel b { animation: none; }
}
</style>

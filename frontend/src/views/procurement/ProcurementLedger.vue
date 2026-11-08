<template>
  <section class="pc-ledger" data-testid="procurement-ledger-page">
    <header class="pc-ledger__head">
      <h1>采购台账</h1>
      <div class="pc-ledger__sum">
        <span>{{ result.total }} 张</span>
        <b data-testid="ledger-total">¥{{ formatMoney(result.total_amount) }}</b>
      </div>
      <button type="button" class="pc-ledger__export" :disabled="exporting" data-testid="ledger-export" @click="exportCsv">
        {{ exporting ? '导出中' : '导出' }}
      </button>
    </header>

    <form class="pc-filters" @submit.prevent="apply">
      <label>关键字<input v-model.trim="filters.keyword" placeholder="物料或单号" data-testid="ledger-keyword" /></label>
      <label>供应商<input v-model.trim="filters.supplier" /></label>
      <label>状态
        <select v-model="filters.status" data-testid="ledger-status">
          <option value="">全部</option>
          <option v-for="(label, code) in STATUS_LABELS" :key="code" :value="code">{{ label }}</option>
        </select>
      </label>
      <label>环节
        <select v-model="filters.step">
          <option value="">全部</option>
          <option v-for="step in meta.steps || []" :key="step.code" :value="step.code">{{ step.label }}</option>
        </select>
      </label>
      <label>类别
        <select v-model="filters.category">
          <option value="">全部</option>
          <option v-for="item in meta.categories || []" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label>提报从<input v-model="filters.date_from" type="date" /></label>
      <label>提报到<input v-model="filters.date_to" type="date" /></label>
      <label class="pc-filters__check"><input v-model="filters.emergency" type="checkbox" data-testid="ledger-emergency" />紧急采购</label>
      <label class="pc-filters__check"><input v-model="filters.overdue" type="checkbox" />已超时</label>
      <div class="pc-filters__actions">
        <button type="submit" class="is-primary" data-testid="ledger-apply">筛选</button>
        <button type="button" @click="reset">清空</button>
      </div>
    </form>

    <p v-if="error" class="pc-ledger__error" role="alert">{{ error }}</p>

    <div class="pc-ledger__table">
      <table data-testid="procurement-ledger">
        <thead>
          <tr>
            <th>单号</th><th>提报</th><th>车间</th><th>物料</th><th>类别</th><th>供应商</th><th class="is-num">金额</th><th>环节</th>
            <th v-if="filters.emergency">补手续期限</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in result.items" :key="row.id" data-testid="ledger-row">
            <td><RouterLink :to="`/procurement/${row.id}`">{{ row.request_no }}</RouterLink></td>
            <td>{{ (row.created_at || '').slice(0, 10) }}<small>{{ row.requester_name }}</small></td>
            <td>{{ row.workshop_name || '-' }}</td>
            <td>{{ row.material_name }}<small v-if="row.specification">{{ row.specification }}</small></td>
            <td>{{ row.category }}</td>
            <td>{{ row.supplier || '-' }}</td>
            <td class="is-num">{{ formatMoney(row.amount) }}</td>
            <td>
              {{ STATUS_LABELS[row.status] && row.status !== 'open' ? STATUS_LABELS[row.status] : row.step_label }}
              <em v-if="row.is_overdue" class="is-danger">超时</em>
              <em v-if="row.is_emergency" class="is-warn">紧急</em>
            </td>
            <td v-if="filters.emergency">{{ row.backfill_due_on || '-' }}</td>
          </tr>
          <tr v-if="!loading && !result.items.length"><td colspan="9" class="is-empty">没有符合条件的单据</td></tr>
        </tbody>
      </table>
    </div>

    <nav v-if="pageCount > 1" class="pc-pager" aria-label="分页">
      <button type="button" :disabled="result.page <= 1" @click="go(result.page - 1)">上一页</button>
      <span>{{ result.page }} / {{ pageCount }}</span>
      <button type="button" :disabled="result.page >= pageCount" data-testid="ledger-next" @click="go(result.page + 1)">下一页</button>
    </nav>
  </section>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { formatApiErrorMessage } from '../../api/index.js'
import { downloadProcurementLedger, fetchProcurementLedger, formatMoney } from '../../api/procurement.js'

const STATUS_LABELS = { open: '在办', archived: '已归档', closed_stock: '库存充足', cancelled: '已撤销' }
const TEXT_KEYS = ['keyword', 'supplier', 'status', 'step', 'category', 'date_from', 'date_to']
const FLAG_KEYS = ['emergency', 'overdue']

const route = useRoute()
const router = useRouter()
const meta = inject('procurementMeta')
const filters = reactive(Object.fromEntries([...TEXT_KEYS.map((key) => [key, '']), ...FLAG_KEYS.map((key) => [key, false])]))
const result = ref({ items: [], total: 0, total_amount: '0', page: 1, page_size: 20 })
const loading = ref(true)
const exporting = ref(false)
const error = ref('')

const pageCount = computed(() => Math.max(1, Math.ceil(result.value.total / result.value.page_size)))

function readQuery() {
  TEXT_KEYS.forEach((key) => { filters[key] = typeof route.query[key] === 'string' ? route.query[key] : '' })
  FLAG_KEYS.forEach((key) => { filters[key] = route.query[key] === 'true' })
}

function params() {
  const query = {}
  TEXT_KEYS.forEach((key) => { if (filters[key]) query[key] = filters[key] })
  FLAG_KEYS.forEach((key) => { if (filters[key]) query[key] = 'true' })
  return query
}

async function load(page = 1) {
  loading.value = true
  error.value = ''
  try {
    result.value = await fetchProcurementLedger({ ...params(), page, page_size: 20 })
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function apply() {
  const next = params()
  if (JSON.stringify(next) === JSON.stringify(route.query)) load(1)
  else router.replace({ query: next })
}

function reset() {
  TEXT_KEYS.forEach((key) => { filters[key] = '' })
  FLAG_KEYS.forEach((key) => { filters[key] = false })
  apply()
}

function go(page) {
  load(page)
}

async function exportCsv() {
  exporting.value = true
  error.value = ''
  try {
    await downloadProcurementLedger(params())
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    exporting.value = false
  }
}

function syncFromRoute() {
  readQuery()
  load(1)
}

watch(() => route.query, () => { if (route.name === 'procurement-ledger') syncFromRoute() })
onMounted(syncFromRoute)
</script>

<style scoped>
.pc-ledger { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; }
.pc-ledger__head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px 24px; }
.pc-ledger__head h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-ledger__sum { display: flex; align-items: baseline; gap: 12px; margin-left: auto; color: var(--xt-text-secondary); }
.pc-ledger__sum b { color: var(--xt-text); font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.pc-ledger__export, .pc-filters__actions button, .pc-pager button { min-height: 44px; padding: 0 16px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; cursor: pointer; }
.pc-ledger__export:disabled, .pc-pager button:disabled { color: var(--xt-text-muted); cursor: default; }
.pc-filters { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); align-items: end; gap: 12px 16px; padding-bottom: 24px; border-bottom: 1px solid var(--xt-border); }
.pc-filters label { display: grid; gap: 6px; min-width: 0; color: var(--xt-text-secondary); font-size: 14px; }
.pc-filters input:not([type='checkbox']), .pc-filters select { box-sizing: border-box; width: 100%; min-width: 0; min-height: 44px; padding: 0 10px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; }
.pc-filters .pc-filters__check { display: flex; align-items: center; gap: 8px; min-height: 44px; color: var(--xt-text); }
.pc-filters__check input { width: 20px; height: 20px; }
.pc-filters__actions { display: flex; gap: 8px; }
.pc-filters__actions .is-primary { border-color: var(--xt-primary); background: var(--xt-primary); color: #fff; font-weight: 600; }
.pc-ledger__error { margin: 0; color: var(--xt-danger); }
.pc-ledger__table { overflow-x: auto; }
.pc-ledger table { width: 100%; min-width: 860px; border-collapse: collapse; }
.pc-ledger th { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--xt-border); color: var(--xt-text-muted); font-size: 12px; font-weight: 400; text-align: left; white-space: nowrap; }
.pc-ledger td { padding: 12px 12px 12px 0; border-bottom: 1px solid var(--xt-border); vertical-align: top; }
.pc-ledger td small { display: block; margin-top: 2px; color: var(--xt-text-muted); font-size: 12px; }
.pc-ledger td a { color: var(--xt-primary); text-decoration: none; }
.pc-ledger td em { margin-left: 6px; font-size: 12px; font-style: normal; }
.pc-ledger .is-danger { color: var(--xt-danger); }
.pc-ledger .is-warn { color: var(--xt-warning); }
.pc-ledger .is-num { font-variant-numeric: tabular-nums; text-align: right; }
.pc-ledger .is-empty { padding: 40px 0; color: var(--xt-text-muted); text-align: center; }
.pc-pager { display: flex; align-items: center; justify-content: flex-end; gap: 12px; color: var(--xt-text-secondary); }
button:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
</style>

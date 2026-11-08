<template>
  <section class="pc-sup" data-testid="procurement-suppliers">
    <header class="pc-sup__head">
      <h1>供应商</h1>
      <button v-if="canEdit && !showForm" type="button" class="is-primary" data-testid="supplier-add" @click="showForm = true">新增</button>
    </header>

    <div class="pc-sup__tabs" role="group" aria-label="状态">
      <button v-for="tab in TABS" :key="tab.value" type="button" :class="{ 'is-on': active === tab.value }" @click="active = tab.value">
        {{ tab.label }} <small>{{ countOf(tab.value) }}</small>
      </button>
    </div>

    <form v-if="canEdit && showForm" class="pc-sup__form" data-testid="supplier-form" @submit.prevent="save">
      <label>名称<input v-model.trim="form.name" required maxlength="128" data-testid="supplier-name" /></label>
      <label>状态
        <select v-model="form.status" data-testid="supplier-status">
          <option v-for="(label, code) in STATUS_LABELS" :key="code" :value="code">{{ label }}</option>
        </select>
      </label>
      <label>联系方式<input v-model.trim="form.contact" maxlength="128" /></label>
      <label>备注<input v-model.trim="form.remark" /></label>
      <div class="pc-sup__actions">
        <button type="submit" class="is-primary" :disabled="busy" data-testid="supplier-save">保存</button>
        <button type="button" @click="clear">取消</button>
      </div>
    </form>
    <p v-if="error" class="pc-sup__error" role="alert" data-testid="supplier-error">{{ error }}</p>

    <div class="pc-sup__table">
      <table>
        <thead>
          <tr><th>名称</th><th>状态</th><th class="is-num">报价</th><th class="is-num">中标</th><th class="is-num">累计金额</th><th>联系方式</th><th>备注</th><th v-if="canEdit" /></tr>
        </thead>
        <tbody>
          <tr v-for="row in visible" :key="row.id" data-testid="supplier-row">
            <td>{{ row.name }}</td>
            <td><span class="pc-sup__status" :class="`is-${row.status}`">{{ STATUS_LABELS[row.status] }}</span></td>
            <td class="is-num">{{ row.quote_count }}</td>
            <td class="is-num">{{ row.win_count }}</td>
            <td class="is-num">{{ formatMoney(row.total_amount) }}</td>
            <td>{{ row.contact || '-' }}</td>
            <td>{{ row.remark || '-' }}</td>
            <td v-if="canEdit"><button type="button" class="pc-sup__edit" @click="edit(row)">修改</button></td>
          </tr>
          <tr v-if="!loading && !visible.length"><td colspan="8" class="is-empty">暂无</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from 'vue'

import { formatApiErrorMessage } from '../../api/index.js'
import { fetchProcurementSuppliers, formatMoney, saveProcurementSupplier } from '../../api/procurement.js'

const STATUS_LABELS = { pending: '待评价', qualified: '合格', blacklisted: '黑名单' }
const TABS = [{ value: '', label: '全部' }, { value: 'pending', label: '待评价' }, { value: 'qualified', label: '合格' }, { value: 'blacklisted', label: '黑名单' }]

const meta = inject('procurementMeta')
const canEdit = computed(() => Boolean(meta.value.can_edit_suppliers))
const rows = ref([])
const active = ref('')
const loading = ref(true)
const busy = ref(false)
const showForm = ref(false)
const error = ref('')
const form = reactive({ id: null, name: '', status: 'qualified', contact: '', remark: '' })

const visible = computed(() => rows.value.filter((row) => !active.value || row.status === active.value))

function countOf(status) {
  return status ? rows.value.filter((row) => row.status === status).length : rows.value.length
}

function clear() {
  Object.assign(form, { id: null, name: '', status: 'qualified', contact: '', remark: '' })
  showForm.value = false
}

function edit(row) {
  Object.assign(form, { id: row.id, name: row.name, status: row.status, contact: row.contact || '', remark: row.remark || '' })
  showForm.value = true
  error.value = ''
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    const { id, ...body } = form
    rows.value = await saveProcurementSupplier(id, body)
    clear()
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    rows.value = await fetchProcurementSuppliers()
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.pc-sup { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; }
.pc-sup__head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.pc-sup__head button { min-height: 44px; padding: 0 20px; border: 0; border-radius: 4px; background: var(--xt-primary); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }
.pc-sup h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-sup__tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.pc-sup__tabs button { min-height: 44px; padding: 0 14px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; cursor: pointer; }
.pc-sup__tabs button.is-on { border-color: var(--xt-primary); background: var(--xt-primary-light); color: var(--xt-primary); font-weight: 600; }
.pc-sup__tabs small { color: var(--xt-text-muted); font-variant-numeric: tabular-nums; }
.pc-sup__form { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); align-items: end; gap: 12px 16px; padding: 20px; border-radius: 4px; background: var(--xt-bg-panel-soft); }
.pc-sup__form label { display: grid; gap: 6px; min-width: 0; color: var(--xt-text-secondary); font-size: 14px; }
.pc-sup__form input, .pc-sup__form select { box-sizing: border-box; width: 100%; min-width: 0; min-height: 44px; padding: 0 10px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; }
.pc-sup__actions { display: flex; gap: 8px; }
.pc-sup__actions button { min-height: 44px; padding: 0 16px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); font: inherit; cursor: pointer; }
.pc-sup__actions .is-primary { border-color: var(--xt-primary); background: var(--xt-primary); color: #fff; font-weight: 600; }
.pc-sup__error { margin: 0; color: var(--xt-danger); }
.pc-sup__table { overflow-x: auto; }
.pc-sup table { width: 100%; min-width: 760px; border-collapse: collapse; }
.pc-sup th { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--xt-border); color: var(--xt-text-muted); font-size: 12px; font-weight: 400; text-align: left; }
.pc-sup td { padding: 10px 12px 10px 0; border-bottom: 1px solid var(--xt-border); }
.pc-sup .is-num { font-variant-numeric: tabular-nums; text-align: right; }
.pc-sup .is-empty { padding: 40px 0; color: var(--xt-text-muted); text-align: center; }
.pc-sup__status.is-qualified { color: var(--xt-success); }
.pc-sup__status.is-pending { color: var(--xt-text-secondary); }
.pc-sup__status.is-blacklisted { color: var(--xt-danger); font-weight: 600; }
.pc-sup__edit { min-height: 44px; padding: 0; border: 0; background: transparent; color: var(--xt-primary); font: inherit; cursor: pointer; }
button:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
</style>

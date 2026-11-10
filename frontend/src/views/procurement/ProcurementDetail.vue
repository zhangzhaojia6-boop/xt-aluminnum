<template>
  <section class="pc-detail" data-testid="procurement-detail">
    <p v-if="loading" class="pc-detail__state" role="status">加载中</p>
    <div v-else-if="loadError" class="pc-detail__state">
      {{ loadError }}
      <button type="button" @click="load">重试</button>
    </div>

    <template v-else-if="item">
      <header class="pc-detail__head">
        <h1>{{ item.material_name }}</h1>
        <p>{{ item.request_no }}<template v-if="item.specification"> · {{ item.specification }}</template> · {{ item.category }}</p>
        <div class="pc-detail__amount">
          <b>¥{{ item.amount }}</b>
          <span>{{ item.purchase_quantity || item.quantity }}{{ item.unit }}</span>
          <span v-if="item.is_emergency" class="pc-detail__tag">紧急采购</span>
        </div>
      </header>

      <div class="pc-track" role="img" :aria-label="`共 16 个环节，当前第 ${item.step_number} 个：${item.step_label}`" data-testid="procurement-track">
        <i v-for="n in 16" :key="n" :class="{ 'is-done': isDone(n), 'is-now': isNow(n) }" />
      </div>
      <p class="pc-detail__status" :class="{ 'is-overdue': item.is_overdue }" data-testid="procurement-status">
        {{ statusText }}
        <small v-if="item.is_overdue">已超时</small>
        <small v-else-if="item.deadline && item.status === 'open'">时限 {{ item.deadline.slice(0, 16).replace('T', ' ') }}</small>
      </p>

      <form v-if="item.can_act" class="pc-panel" data-testid="procurement-panel" @submit.prevent>
        <h2>{{ item.step_label }}</h2>

        <template v-if="step === 'draft'">
          <label v-if="item.is_emergency" class="pc-field">向分管领导电话报告的记录<textarea v-model.trim="form.emergency_report" rows="2" /></label>
          <button class="pc-go" type="button" :disabled="busy" data-testid="pc-submit" @click="run('submit', pick('emergency_report'))">提交审批</button>
          <button class="pc-plain" type="button" :disabled="busy" @click="run('cancel')">撤销</button>
        </template>

        <template v-else-if="step === 'stock_review'">
          <div class="pc-row">
            <label class="pc-field">库存数量<input v-model="form.stock_quantity" type="number" inputmode="decimal" step="any" min="0" data-testid="pc-stock" /></label>
            <label class="pc-field">可领用数量<input v-model="form.available_quantity" type="number" inputmode="decimal" step="any" min="0" /></label>
          </div>
          <button class="pc-go" type="button" :disabled="busy" @click="run('confirm_stock', pick('stock_quantity', 'available_quantity'))">确认库存</button>
        </template>

        <template v-else-if="step === 'quotation'">
          <div class="pc-tabs">
            <button type="button" :class="{ 'is-on': !exemption }" @click="exemption = false">比价</button>
            <button type="button" :class="{ 'is-on': exemption }" @click="exemption = true">询价豁免</button>
          </div>
          <template v-if="!exemption">
            <div v-for="(quote, index) in quotes" :key="index" class="pc-quote">
              <label class="pc-quote__pick"><input v-model="selected" type="radio" :value="index" :aria-label="`选定第 ${index + 1} 家`" />选定</label>
              <input v-model.trim="quote.supplier" placeholder="供应商" aria-label="供应商" list="pc-supplier-options" />
              <input v-model="quote.unit_price" type="number" inputmode="decimal" step="any" min="0" placeholder="单价" aria-label="单价" />
              <button v-if="quotes.length > 1" type="button" aria-label="删除这家" @click="removeQuote(index)">×</button>
            </div>
            <datalist id="pc-supplier-options"><option v-for="name in supplierOptions" :key="name" :value="name" /></datalist>
            <button class="pc-plain" type="button" @click="quotes.push({ supplier: '', unit_price: '' })">再加一家</button>
            <button class="pc-go" type="button" :disabled="busy" data-testid="pc-quotes" @click="run('submit_quotes', { quotes, selected_index: selected })">提交比价</button>
          </template>
          <template v-else>
            <label class="pc-field">豁免理由
              <select v-model="form.reason">
                <option value="独家供应">独家供应</option>
                <option value="生产线紧急抢修">生产线紧急抢修</option>
                <option value="年度框架协议">年度框架协议</option>
              </select>
            </label>
            <div class="pc-row">
              <label class="pc-field">供应商<input v-model.trim="form.supplier" /></label>
              <label class="pc-field">单价<input v-model="form.unit_price" type="number" inputmode="decimal" step="any" min="0" /></label>
            </div>
            <button class="pc-go" type="button" :disabled="busy" @click="run('request_exemption', pick('reason', 'supplier', 'unit_price'))">提交豁免审批</button>
          </template>
          <DocUpload label="上传报价单" doc-type="quote" :busy="busy" @pick="upload" />
        </template>

        <template v-else-if="step === 'contract_draft'">
          <div class="pc-tabs">
            <button type="button" :class="{ 'is-on': form.doc_kind === 'contract' }" @click="form.doc_kind = 'contract'">合同</button>
            <button v-if="smallPurchase" type="button" :class="{ 'is-on': form.doc_kind === 'order' }" @click="form.doc_kind = 'order'">采购订单</button>
          </div>
          <div class="pc-row">
            <label class="pc-field">编号<input v-model.trim="form.contract_no" /></label>
            <label class="pc-field">金额（元）<input v-model="form.amount" type="number" inputmode="decimal" step="any" min="0" /></label>
          </div>
          <template v-if="form.doc_kind === 'contract'">
            <label class="pc-check"><input v-model="form.standard_text" type="checkbox" />使用法务审定的标准文本</label>
            <DocUpload label="上传合同稿" doc-type="contract_draft" :busy="busy" @pick="upload" />
          </template>
          <button class="pc-go" type="button" :disabled="busy" @click="run('submit_contract', pick('doc_kind', 'contract_no', 'amount', 'standard_text'))">提交审核</button>
        </template>

        <template v-else-if="step === 'contract_sign'">
          <DocUpload v-if="item.details?.contract?.doc_kind === 'contract'" label="上传盖章合同" doc-type="contract" :busy="busy" @pick="upload" />
          <button class="pc-go" type="button" :disabled="busy" @click="run('sign')">确认已签订，可以供货</button>
        </template>

        <template v-else-if="step === 'gate_registration'">
          <label class="pc-field">送货单位<input v-model.trim="form.supplier" /></label>
          <label class="pc-field">货物名称<input v-model.trim="form.goods" /></label>
          <div class="pc-row">
            <label class="pc-field">数量<input v-model="form.quantity" type="number" inputmode="decimal" step="any" min="0" /></label>
            <label class="pc-field">车牌号<input v-model.trim="form.plate_no" /></label>
          </div>
          <DocUpload label="拍车牌和货物" doc-type="gate_photo" :busy="busy" capture @pick="upload" />
          <button class="pc-go" type="button" :disabled="busy" @click="run('register', pick('supplier', 'goods', 'quantity', 'plate_no'))">生成到货单</button>
        </template>

        <template v-else-if="step === 'acceptance'">
          <label class="pc-field">验收数量<input v-model="form.accepted_quantity" type="number" inputmode="decimal" step="any" min="0" /></label>
          <label class="pc-check"><input v-model="form.needs_quality_check" type="checkbox" />需要质检（生产物料、关键备件）</label>
          <DocUpload label="上传供应商送货单" doc-type="delivery_note" :busy="busy" capture @pick="upload" />
          <button class="pc-go" type="button" :disabled="busy" @click="run('accept', pick('accepted_quantity', 'needs_quality_check'))">验收合格，生成入库单</button>
          <details class="pc-more">
            <summary>验收不合格</summary>
            <label class="pc-field">拒收原因<input v-model.trim="form.reason" /></label>
            <DocUpload label="上传供应商签字的拒收说明" doc-type="rejection_note" :busy="busy" capture @pick="upload" />
            <button class="pc-plain" type="button" :disabled="busy" @click="run('refuse', pick('reason'))">拒收</button>
          </details>
        </template>

        <template v-else-if="step === 'document_collection'">
          <DocUpload label="上传供应商送货单" doc-type="delivery_note" :busy="busy" @pick="upload" />
          <DocUpload label="上传增值税发票" doc-type="invoice" :busy="busy" @pick="upload" />
          <label class="pc-field">发票号<input v-model.trim="form.invoice_no" /></label>
          <div class="pc-row">
            <label class="pc-field">发票金额<input v-model="form.invoice_amount" type="number" inputmode="decimal" step="any" min="0" /></label>
            <label class="pc-field">付款金额<input v-model="form.payment_amount" type="number" inputmode="decimal" step="any" min="0" /></label>
          </div>
          <button class="pc-go" type="button" :disabled="busy" data-testid="pc-payment" @click="run('submit_payment', pick('invoice_no', 'invoice_amount', 'payment_amount'))">发起付款</button>
        </template>

        <template v-else-if="step === 'payment_booking'">
          <label class="pc-field">凭证号<input v-model.trim="form.voucher_no" /></label>
          <button class="pc-go" type="button" :disabled="busy" @click="run('book', pick('voucher_no'))">登记付款并归档</button>
        </template>

        <template v-else>
          <label v-if="step === 'finance_contract_review'" class="pc-field">签约主体<input v-model.trim="form.signing_entity" /></label>
          <label class="pc-field">意见（驳回必填）<textarea v-model.trim="form.comment" rows="2" data-testid="pc-comment" /></label>
          <div class="pc-row">
            <button class="pc-plain" type="button" :disabled="busy" data-testid="pc-reject" @click="run('reject')">驳回</button>
            <button class="pc-go" type="button" :disabled="busy" data-testid="pc-approve" @click="run('approve', pick('signing_entity'))">同意</button>
          </div>
        </template>

        <p v-if="error" class="pc-error" role="alert" data-testid="pc-error">{{ error }}</p>
      </form>

      <details v-if="item.can_void" class="pc-void" data-testid="procurement-void">
        <summary>作废这张单</summary>
        <label class="pc-field">作废理由<textarea v-model.trim="voidReason" rows="2" data-testid="pc-void-reason" /></label>
        <button class="pc-plain" type="button" :disabled="busy || !voidReason" data-testid="pc-void-submit" @click="voidIt">确认作废</button>
      </details>

      <section class="pc-block">
        <h2>申请内容</h2>
        <dl class="pc-facts">
          <div><dt>申请数量</dt><dd>{{ item.quantity }}{{ item.unit }}</dd></div>
          <div v-if="item.purchase_quantity"><dt>采购数量</dt><dd>{{ item.purchase_quantity }}{{ item.unit }}</dd></div>
          <div><dt>预估单价</dt><dd>¥{{ item.estimated_unit_price }}</dd></div>
          <div v-if="item.needed_by"><dt>需求到货</dt><dd>{{ item.needed_by }}</dd></div>
          <div v-if="item.supplier"><dt>供应商</dt><dd>{{ item.supplier }}</dd></div>
          <div><dt>用途</dt><dd>{{ item.purpose }}</dd></div>
        </dl>
      </section>

      <section v-if="item.quotes.length" class="pc-block">
        <h2>比价</h2>
        <ul class="pc-quotes">
          <li v-for="(quote, index) in latestQuotes" :key="index" :class="{ 'is-on': quote.is_selected }">
            <span>{{ quote.supplier }}</span>
            <i :style="{ width: `${quoteRatio(quote)}%` }" />
            <b>¥{{ quote.unit_price }}</b>
          </li>
        </ul>
      </section>

      <section class="pc-block" data-testid="procurement-checklist">
        <h2>九类单据 <small>{{ presentCount }}/{{ item.document_checklist.length }}</small></h2>
        <ul class="pc-docs">
          <li v-for="doc in item.document_checklist" :key="doc.code" :class="{ 'is-on': doc.present }">
            <i aria-hidden="true" />
            <span>{{ doc.label }}</span>
            <small>{{ doc.present ? '已有' : '缺' }}</small>
          </li>
        </ul>
        <ul v-if="item.documents.length" class="pc-files">
          <li v-for="file in item.documents" :key="file.id">
            <button type="button" @click="openProcurementDocument(file.id)">{{ file.file_name }}</button>
          </li>
        </ul>
      </section>

      <section class="pc-block">
        <h2>办理记录</h2>
        <ol class="pc-logs">
          <li v-for="(log, index) in item.logs" :key="index">
            <span>{{ log.step_label }} · {{ ACTION_LABELS[log.action] || log.action }}</span>
            <small>{{ log.actor_name }}<template v-if="log.at"> · {{ log.at.slice(0, 16).replace('T', ' ') }}</template></small>
            <p v-if="log.comment">{{ log.comment }}</p>
          </li>
        </ol>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { formatApiErrorMessage } from '../../api/index.js'
import {
  actOnProcurementRequest,
  voidProcurementRequest,
  fetchProcurementRequest,
  fetchProcurementSuppliers,
  openProcurementDocument,
  uploadProcurementDocument,
} from '../../api/procurement.js'
import DocUpload from './ProcurementDocUpload.vue'

const ACTION_LABELS = {
  create: '建单', submit: '提交', cancel: '撤销', approve: '同意', reject: '驳回', confirm_stock: '确认库存',
  submit_quotes: '提交比价', request_exemption: '申请豁免', submit_contract: '提交合同', sign: '确认签订',
  void: '作废', register: '进厂登记', accept: '验收合格', refuse: '拒收', submit_payment: '发起付款', book: '付款入账', upload: '上传单据',
}
const FINAL_STATUS = { archived: '已付款归档', closed_stock: '库存充足，已驳回，由车间直接领用', cancelled: '已撤销' }

const route = useRoute()
const item = ref(null)
const loading = ref(true)
const loadError = ref('')
const busy = ref(false)
const error = ref('')
const exemption = ref(false)
const voidReason = ref('')
const supplierOptions = ref([])
const selected = ref(0)
const quotes = ref([{ supplier: '', unit_price: '' }])
const form = reactive({ doc_kind: 'contract', reason: '独家供应' })

const step = computed(() => item.value?.current_step)
const smallPurchase = computed(() => Number(item.value?.amount) < 5000)
const presentCount = computed(() => item.value.document_checklist.filter((doc) => doc.present).length)
const statusText = computed(() => FINAL_STATUS[item.value.status] || `第 ${item.value.step_number} 步，共 16 步：${item.value.step_label}`)
const latestQuotes = computed(() => {
  const round = Math.max(...item.value.quotes.map((quote) => quote.round_no))
  return item.value.quotes.filter((quote) => quote.round_no === round)
})

function isDone(number) {
  return item.value.status === 'archived' || number < item.value.step_number
}

function isNow(number) {
  return item.value.status === 'open' && number === item.value.step_number
}

function quoteRatio(quote) {
  const top = Math.max(...latestQuotes.value.map((row) => Number(row.unit_price)))
  return top > 0 ? (Number(quote.unit_price) / top) * 100 : 0
}

function pick(...keys) {
  return Object.fromEntries(keys.filter((key) => form[key] !== undefined && form[key] !== '').map((key) => [key, form[key]]))
}

function removeQuote(index) {
  quotes.value.splice(index, 1)
  if (selected.value >= quotes.value.length) selected.value = 0
}

function resetForm() {
  Object.keys(form).forEach((key) => { delete form[key] })
  form.doc_kind = smallPurchase.value ? 'order' : 'contract'
  form.reason = step.value === 'quotation' ? '独家供应' : ''
  error.value = ''
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    item.value = await fetchProcurementRequest(route.params.id)
    resetForm()
  } catch (err) {
    loadError.value = formatApiErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function run(action, payload = {}) {
  busy.value = true
  error.value = ''
  try {
    item.value = await actOnProcurementRequest(item.value.id, {
      action,
      expected_step: item.value.current_step,
      comment: form.comment || null,
      payload,
    })
    resetForm()
  } catch (err) {
    error.value = formatApiErrorMessage(err)
    if (err?.response?.status === 409) await load()
  } finally {
    busy.value = false
  }
}

async function voidIt() {
  busy.value = true
  error.value = ''
  try {
    item.value = await voidProcurementRequest(item.value.id, voidReason.value)
    voidReason.value = ''
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    busy.value = false
  }
}

async function loadSupplierOptions() {
  try {
    const rows = await fetchProcurementSuppliers()
    supplierOptions.value = rows.filter((row) => row.status !== 'blacklisted').map((row) => row.name)
  } catch {
    supplierOptions.value = []
  }
}

async function upload(docType, file) {
  busy.value = true
  error.value = ''
  try {
    await uploadProcurementDocument(item.value.id, docType, file)
    item.value = await fetchProcurementRequest(item.value.id)
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    busy.value = false
  }
}

watch(() => route.params.id, (id) => { if (id) load() })
watch(() => (item.value?.can_act ? step.value : null), (value) => { if (value === 'quotation') loadSupplierOptions() })
onMounted(load)
</script>

<style scoped>
.pc-detail { display: grid; grid-template-columns: minmax(0, 1fr); gap: 32px; max-width: 720px; }
.pc-detail__state { padding: 40px 0; color: var(--xt-text-secondary); text-align: center; }
.pc-detail__state button { min-height: 44px; margin-left: 12px; padding: 0 16px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); font: inherit; cursor: pointer; }
.pc-detail__head h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-detail__head p { margin: 4px 0 0; color: var(--xt-text-muted); }
.pc-detail__amount { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 12px; margin-top: 16px; color: var(--xt-text-secondary); }
.pc-detail__amount b { color: var(--xt-text); font-size: 40px; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.pc-detail__tag { color: var(--xt-warning); font-weight: 600; }

.pc-track { display: grid; grid-template-columns: repeat(16, minmax(0, 1fr)); gap: 3px; margin-bottom: -20px; }
.pc-track i { display: block; height: 10px; border-radius: 2px; background: var(--xt-bg-depth); }
.pc-track i.is-done { background: var(--xt-primary); }
.pc-track i.is-now { background: var(--xt-warning); }
.pc-detail__status { margin: 0; color: var(--xt-text-secondary); }
.pc-detail__status small { margin-left: 8px; color: var(--xt-text-muted); font-size: 14px; }
.pc-detail__status.is-overdue small { color: var(--xt-danger); font-weight: 600; }

.pc-panel { display: grid; gap: 16px; padding: 24px 20px; border-radius: 4px; background: var(--xt-bg-panel-soft); }
.pc-panel h2, .pc-block h2 { margin: 0; font-size: 20px; font-weight: 600; }
.pc-block h2 small { margin-left: 8px; color: var(--xt-text-muted); font-size: 14px; font-weight: 400; font-variant-numeric: tabular-nums; }
.pc-field { display: grid; gap: 8px; min-width: 0; color: var(--xt-text-secondary); font-size: 14px; }
.pc-field input, .pc-field select, .pc-field textarea, .pc-quote input:not([type='radio']) { box-sizing: border-box; width: 100%; min-height: 52px; padding: 0 14px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; font-size: 18px; }
.pc-field textarea { padding: 12px 14px; }
.pc-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.pc-check { display: flex; align-items: center; gap: 10px; min-height: 44px; }
.pc-check input { width: 20px; height: 20px; }
.pc-go, .pc-plain { min-height: 56px; border-radius: 4px; font: inherit; font-size: 18px; cursor: pointer; touch-action: manipulation; }
.pc-go { border: 0; background: var(--xt-primary-solid, var(--xt-primary)); color: #fff; font-weight: 600; }
.pc-go:disabled { background: var(--xt-bg-depth); color: var(--xt-text-muted); cursor: default; }
.pc-plain { border: 1px solid var(--xt-border); background: var(--xt-bg-page); color: var(--xt-text); }
.pc-tabs { display: flex; gap: 8px; }
.pc-tabs button { min-height: 44px; padding: 0 16px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); font: inherit; cursor: pointer; }
.pc-tabs button.is-on { border-color: var(--xt-primary); background: var(--xt-primary-light); color: var(--xt-primary); font-weight: 600; }
.pc-quote { display: grid; grid-template-columns: auto minmax(0, 2fr) minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.pc-quote__pick { display: inline-flex; align-items: center; gap: 4px; min-height: 44px; font-size: 14px; }
.pc-quote button { width: 44px; height: 44px; border: 0; background: transparent; color: var(--xt-text-muted); font-size: 20px; cursor: pointer; }
.pc-more summary { min-height: 44px; color: var(--xt-danger); cursor: pointer; }
.pc-more { display: grid; gap: 12px; }
.pc-error { margin: 0; color: var(--xt-danger); }

.pc-void { display: grid; gap: 12px; }
.pc-void summary { min-height: 44px; color: var(--xt-danger); cursor: pointer; }
.pc-block { display: grid; gap: 16px; }
.pc-facts { display: grid; margin: 0; }
.pc-facts div { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--xt-border); }
.pc-facts dt { flex: none; color: var(--xt-text-secondary); }
.pc-facts dd { margin: 0; font-variant-numeric: tabular-nums; text-align: right; }
.pc-quotes { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
.pc-quotes li { position: relative; display: flex; justify-content: space-between; gap: 16px; padding: 10px 12px; overflow: hidden; }
.pc-quotes li i { position: absolute; inset: 0 auto 0 0; z-index: 0; background: var(--xt-bg-panel-soft); }
.pc-quotes li.is-on i { background: var(--xt-primary-light); }
.pc-quotes span, .pc-quotes b { position: relative; z-index: 1; }
.pc-quotes li.is-on span, .pc-quotes li.is-on b { color: var(--xt-primary); font-weight: 600; }
.pc-quotes b { font-weight: 400; font-variant-numeric: tabular-nums; }
.pc-docs { display: grid; margin: 0; padding: 0; list-style: none; }
.pc-docs li { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--xt-border); color: var(--xt-text-secondary); }
.pc-docs i { width: 10px; height: 10px; border-radius: 50%; background: var(--xt-bg-depth); }
.pc-docs small { color: var(--xt-warning); }
.pc-docs li.is-on { color: var(--xt-text); }
.pc-docs li.is-on i { background: var(--xt-success); }
.pc-docs li.is-on small { color: var(--xt-success); }
.pc-files { margin: 0; padding: 0; list-style: none; }
.pc-files button { min-height: 44px; padding: 0; border: 0; background: transparent; color: var(--xt-primary); font: inherit; text-align: left; cursor: pointer; }
.pc-logs { display: grid; gap: 16px; margin: 0; padding: 0; list-style: none; }
.pc-logs li { display: grid; gap: 2px; }
.pc-logs small { color: var(--xt-text-muted); font-size: 12px; }
.pc-logs p { margin: 4px 0 0; color: var(--xt-text-secondary); }
button:focus-visible, summary:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
</style>

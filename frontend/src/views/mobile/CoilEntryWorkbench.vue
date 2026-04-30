<template>
  <div class="mobile-shell mobile-shell--coil" data-testid="coil-entry-workbench">
    <div class="coil-identity" :style="{ '--role-color': 'var(--m-role-operator)' }">
      <div class="coil-identity__main">
        <strong>{{ machineName }}</strong>
        <span>{{ workshopName }}</span>
      </div>
      <div class="coil-identity__shift">
        <span>{{ shiftName }}</span>
        <span>{{ businessDate }}</span>
      </div>
    </div>

    <div class="coil-operator panel">
      <label>操作人</label>
      <el-input
        v-model="operatorName"
        placeholder="姓名"
        @blur="saveOperatorName"
      />
    </div>

    <div class="coil-summary">
      <article class="coil-summary__item">
        <span>已录入</span>
        <strong>{{ coilList.length }}</strong>
        <span>卷</span>
      </article>
      <article class="coil-summary__item">
        <span>总投入</span>
        <strong>{{ totalInput }}</strong>
        <span>kg</span>
      </article>
      <article class="coil-summary__item">
        <span>总产出</span>
        <strong>{{ totalOutput }}</strong>
        <span>kg</span>
      </article>
      <article class="coil-summary__item">
        <span>成品率</span>
        <strong>{{ yieldRate }}</strong>
        <span>%</span>
      </article>
    </div>

    <div class="coil-list" v-if="coilList.length">
      <div
        v-for="coil in coilList"
        :key="coil.id || coil.tracking_card_no"
        class="coil-list__item"
      >
        <div class="coil-list__left">
          <strong>{{ coil.tracking_card_no }}</strong>
          <span>{{ coil.alloy_grade || '-' }} · {{ coil.output_spec || '-' }}</span>
        </div>
        <div class="coil-list__right">
          <span>{{ coil.input_weight || 0 }} → {{ coil.output_weight || 0 }} kg</span>
        </div>
      </div>
    </div>
    <div v-else class="coil-empty panel">
      本班次暂无录入记录。
    </div>

    <div class="coil-actions">
      <el-button type="primary" size="large" class="xt-pressable" @click="showEntryDialog = true">
        录入新卷
      </el-button>
    </div>

    <el-dialog
      v-model="showEntryDialog"
      title="录入新卷"
      :close-on-click-modal="false"
      width="92%"
      class="coil-dialog"
    >
      <div class="mobile-form-grid">
        <div class="mobile-field mobile-field-wide">
          <label><span class="mobile-required">*</span> 坯料卷号</label>
          <el-input v-model="form.tracking_card_no" placeholder="手工输入或扫码" />
        </div>
        <div class="mobile-field">
          <label><span class="mobile-required">*</span> 合金牌号</label>
          <el-input v-model="form.alloy_grade" placeholder="如 1060、3003" />
        </div>
        <div class="mobile-field">
          <label>输入规格</label>
          <el-input v-model="form.input_spec" placeholder="厚×宽" />
        </div>
        <div class="mobile-field">
          <label>输出规格</label>
          <el-input v-model="form.output_spec" placeholder="厚×宽" />
        </div>
        <div class="mobile-field">
          <label><span class="mobile-required">*</span> 投入量(kg)</label>
          <el-input v-model.number="form.input_weight" type="number" inputmode="decimal" />
        </div>
        <div class="mobile-field">
          <label><span class="mobile-required">*</span> 产出量(kg)</label>
          <el-input v-model.number="form.output_weight" type="number" inputmode="decimal" />
        </div>
        <div class="mobile-field">
          <label>废料量(kg)</label>
          <el-input :model-value="suggestedScrap" disabled />
          <span class="mobile-field-unit">自动 = 投入 - 产出</span>
        </div>
        <div class="mobile-field mobile-field-wide">
          <label>备注</label>
          <el-input v-model="form.operator_notes" type="textarea" :rows="2" />
        </div>
      </div>
      <template #footer>
        <el-button @click="showEntryDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" class="xt-pressable" @click="submitCoil">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchCurrentShift, fetchMobileBootstrap } from '../../api/mobile.js'
import { useAuthStore } from '../../stores/auth.js'
import { api } from '../../api/index.js'

const route = useRoute()
const auth = useAuthStore()

const bootstrap = ref({})
const currentShift = ref({})
const coilList = ref([])
const showEntryDialog = ref(false)
const submitting = ref(false)
const operatorName = ref(localStorage.getItem('xt_operator_name') || '')

const machineName = computed(() => currentShift.value?.machine_name || bootstrap.value?.machine_name || '-')
const workshopName = computed(() => currentShift.value?.workshop_name || bootstrap.value?.workshop_name || '-')
const shiftName = computed(() => currentShift.value?.shift_name || currentShift.value?.shift_code || '-')
const businessDate = computed(() => currentShift.value?.business_date || '-')

const totalInput = computed(() => coilList.value.reduce((sum, c) => sum + (Number(c.input_weight) || 0), 0))
const totalOutput = computed(() => coilList.value.reduce((sum, c) => sum + (Number(c.output_weight) || 0), 0))
const yieldRate = computed(() => {
  if (!totalInput.value) return '-'
  return ((totalOutput.value / totalInput.value) * 100).toFixed(1)
})

const emptyForm = () => ({
  tracking_card_no: '',
  alloy_grade: '',
  input_spec: '',
  output_spec: '',
  input_weight: null,
  output_weight: null,
  operator_notes: '',
})
const form = ref(emptyForm())
const suggestedScrap = computed(() => {
  const inp = Number(form.value.input_weight) || 0
  const out = Number(form.value.output_weight) || 0
  return inp > 0 && out > 0 ? (inp - out).toFixed(1) : ''
})

function saveOperatorName() {
  if (operatorName.value) {
    localStorage.setItem('xt_operator_name', operatorName.value)
  }
}

async function loadData() {
  try {
    const [bs, cs] = await Promise.all([fetchMobileBootstrap(), fetchCurrentShift()])
    bootstrap.value = bs
    currentShift.value = cs
    await loadCoils()
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

async function loadCoils() {
  const bd = currentShift.value?.business_date
  const sid = currentShift.value?.shift_id
  if (!bd || !sid) return
  try {
    const { data } = await api.get(`/mobile/coil-list/${bd}/${sid}`)
    coilList.value = data || []
  } catch {
    coilList.value = []
  }
}

async function submitCoil() {
  if (!form.value.tracking_card_no || !form.value.input_weight || !form.value.output_weight) {
    ElMessage.warning('请填写必填字段')
    return
  }
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      scrap_weight: Number(suggestedScrap.value) || 0,
      operator_name: operatorName.value,
      business_date: currentShift.value?.business_date,
      shift_id: currentShift.value?.shift_id,
    }
    await api.post('/mobile/coil-entry', payload)
    ElMessage.success('提交成功')
    form.value = emptyForm()
    showEntryDialog.value = false
    await loadCoils()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.mobile-shell--coil {
  display: grid;
  gap: var(--xt-space-3);
}

.coil-identity {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: var(--xt-space-4);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-ink);
  border-left: 3px solid var(--role-color, var(--xt-primary));
  box-shadow: var(--xt-shadow-md);
}

.coil-identity__main {
  display: grid;
  gap: 2px;
}

.coil-identity__main strong {
  color: rgba(255, 255, 255, 0.92);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-xl);
  font-weight: 850;
  letter-spacing: -0.012em;
}

.coil-identity__main span,
.coil-identity__shift span {
  color: rgba(255, 255, 255, 0.55);
  font-size: var(--xt-text-sm);
}

.coil-identity__shift {
  display: grid;
  gap: 2px;
  text-align: right;
}

.coil-identity__shift span:first-child {
  color: rgba(255, 255, 255, 0.82);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.coil-operator {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
}

.coil-operator label {
  font-weight: 850;
  font-size: var(--xt-text-lg);
  white-space: nowrap;
}

.coil-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.coil-summary__item {
  display: grid;
  gap: 2px;
  padding: var(--xt-space-3);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  box-shadow: var(--xt-shadow-xs);
}

.coil-summary__item span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.coil-summary__item strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.012em;
}

.coil-list {
  display: grid;
  gap: 1px;
  background: var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  overflow: hidden;
  box-shadow: var(--xt-shadow-sm);
}

.coil-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
}

.coil-list__left {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.coil-list__left strong {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 700;
  color: var(--xt-text);
}

.coil-list__left span {
  font-size: var(--xt-text-sm);
  color: var(--xt-text-secondary);
}

.coil-list__right {
  text-align: right;
  white-space: nowrap;
}

.coil-list__right span {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-sm);
  font-variant-numeric: tabular-nums;
  color: var(--xt-text-secondary);
}

.coil-empty {
  padding: var(--xt-space-6);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-lg);
}

.coil-actions {
  position: sticky;
  bottom: calc(var(--xt-tabbar-height) + env(safe-area-inset-bottom, 0px) + 8px);
  z-index: 10;
}

.coil-actions .el-button {
  width: 100%;
  min-height: 52px;
  border-radius: var(--xt-radius-lg);
  font-size: var(--xt-text-lg);
  font-weight: 900;
  box-shadow: var(--xt-shadow-md);
}

@media (max-width: 400px) {
  .coil-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
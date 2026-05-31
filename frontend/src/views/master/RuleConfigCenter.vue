<template>
  <section class="page-stack rule-config-center" data-testid="rule-config-page" aria-labelledby="rule-config-title">
    <header class="rule-config-center__hero">
      <div class="rule-config-center__title-block">
        <span class="rule-config-center__eyebrow">RULE GOVERNANCE MATRIX</span>
        <h1 id="rule-config-title">规则配置</h1>
      </div>
      <div class="rule-config-center__hero-actions">
        <el-button class="rule-config-center__refresh" :loading="loading" data-testid="rule-config-refresh" @click="loadRules">刷新</el-button>
      </div>
    </header>

    <section class="rule-config-center__status" aria-label="规则配置状态">
      <article
        v-for="stat in ruleStats"
        :key="stat.label"
        class="rule-config-center__stat"
        :class="`is-${stat.tone}`"
      >
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
        <small>{{ stat.meta }}</small>
      </article>
    </section>

    <section class="rule-config-center__layout">
      <aside class="rule-config-center__cabin" aria-label="规则作用域">
        <div class="rule-config-center__cabin-head">
          <span>SCOPE NODE</span>
          <strong>作用域</strong>
        </div>
        <el-select
          v-model="selectedScope"
          class="rule-config-center__scope-select"
          filterable
          data-testid="rule-config-scope"
          @change="loadRules"
        >
          <el-option label="全厂默认" value="factory:" />
          <el-option
            v-for="workshop in activeWorkshops"
            :key="workshop.code"
            :label="`${workshop.name} (${workshop.code})`"
            :value="`workshop:${workshop.code}`"
          />
        </el-select>

        <div class="rule-config-center__scope-card">
          <span>当前口径</span>
          <strong>{{ scopeTitle }}</strong>
          <ReferenceStatusTag :status="hasOverrides ? 'warning' : 'success'" :label="hasOverrides ? '车间覆盖' : '继承默认'" />
        </div>

        <div class="rule-config-center__health">
          <div>
            <span>覆盖规则</span>
            <strong>{{ overrideCount }}</strong>
          </div>
          <div>
            <span>默认继承</span>
            <strong>{{ inheritedCount }}</strong>
          </div>
        </div>
      </aside>

      <section class="rule-surface">
        <div class="rule-surface__head">
          <div>
            <span>RULE MATRIX</span>
            <strong>规则矩阵</strong>
          </div>
          <div class="rule-surface__state">
            <small>{{ scopeTitle }}</small>
            <ReferenceStatusTag :status="dirtyCount ? 'warning' : 'success'" :label="dirtyCount ? `${dirtyCount} 项待保存` : '已同步'" />
          </div>
        </div>

        <el-table
          v-loading="loading"
          :data="ruleRows"
          :row-class-name="ruleRowClassName"
          class="rule-table"
          row-key="key"
          data-testid="rule-config-table"
        >
          <el-table-column prop="key" label="规则键" min-width="220">
            <template #default="{ row }">
              <div class="rule-key">
                <strong>{{ row.key }}</strong>
                <span>{{ ruleLabels[row.key] || row.key }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="当前值" width="120" align="right">
            <template #default="{ row }">
              <span class="rule-value">{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="110">
            <template #default="{ row }">
              <ReferenceStatusTag :status="row.source === 'override' ? 'warning' : 'success'" :label="row.source === 'override' ? '覆盖' : '默认'" />
            </template>
          </el-table-column>
          <el-table-column label="调整" width="170" align="right">
            <template #default="{ row }">
              <el-input-number
                v-model="row.editValue"
                :precision="precisionFor(row)"
                :step="stepFor(row)"
                :controls="false"
                class="rule-input"
                data-testid="rule-config-value"
              />
            </template>
          </el-table-column>
          <el-table-column label="" width="96" align="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                class="rule-save"
                :loading="savingKey === row.key"
                :disabled="!hasRuleChanged(row)"
                data-testid="rule-config-save"
                @click="saveRule(row)"
              >
                保存
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="rule-config-center__mobile-rules" aria-label="移动端规则列表">
          <article
            v-for="row in ruleRows"
            :key="row.key"
            class="rule-config-center__mobile-rule"
            :class="{ 'is-dirty': hasRuleChanged(row) }"
          >
            <header>
              <div class="rule-key">
                <strong>{{ row.key }}</strong>
                <span>{{ ruleLabels[row.key] || row.key }}</span>
              </div>
              <ReferenceStatusTag :status="row.source === 'override' ? 'warning' : 'success'" :label="row.source === 'override' ? '覆盖' : '默认'" />
            </header>
            <div class="rule-config-center__mobile-values">
              <div>
                <span>当前值</span>
                <strong>{{ row.value }}</strong>
              </div>
              <el-input-number
                v-model="row.editValue"
                :precision="precisionFor(row)"
                :step="stepFor(row)"
                :controls="false"
                class="rule-input"
                data-testid="rule-config-mobile-value"
              />
            </div>
            <el-button
              type="primary"
              class="rule-save"
              :loading="savingKey === row.key"
              :disabled="!hasRuleChanged(row)"
              data-testid="rule-config-mobile-save"
              @click="saveRule(row)"
            >
              保存
            </el-button>
          </article>
        </div>
      </section>
    </section>

    <section class="rule-config-center__rail" aria-label="规则链路状态">
      <div>
        <span>DEFAULT LAYER</span>
        <strong>全厂默认</strong>
      </div>
      <i></i>
      <div>
        <span>WORKSHOP LAYER</span>
        <strong>车间覆盖</strong>
      </div>
      <i></i>
      <div>
        <span>VALIDATION LAYER</span>
        <strong>自动校验</strong>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { fetchRuleConfigs, fetchWorkshops, updateRuleConfig, upsertRuleConfig } from '../../api/master'

const selectedScope = ref('factory:')
const workshops = ref([])
const ruleRows = ref([])
const loading = ref(false)
const savingKey = ref('')

const ruleLabels = {
  MIN_ATTENDANCE: '最低出勤人数',
  MAX_ATTENDANCE: '最高出勤人数',
  MIN_WEIGHT: '最低重量',
  MAX_SINGLE_SHIFT_WEIGHT: '单班重量上限',
  MIN_ENERGY: '最低能耗',
  MAX_ELECTRICITY_DAILY: '日电耗上限',
  MAX_GAS_DAILY: '日燃气上限',
  RECONCILIATION_TOLERANCE_PERCENT: '核对差异率'
}

const activeWorkshops = computed(() => workshops.value.filter((item) => item.is_active !== false))
const overrideCount = computed(() => ruleRows.value.filter((item) => item.source === 'override').length)
const totalRuleCount = computed(() => ruleRows.value.length)
const inheritedCount = computed(() => Math.max(totalRuleCount.value - overrideCount.value, 0))
const dirtyCount = computed(() => ruleRows.value.filter((item) => hasRuleChanged(item)).length)
const scopeParts = computed(() => {
  const [scope_type, scope_key = ''] = selectedScope.value.split(':')
  return {
    scope_type,
    scope_key: scope_key || null
  }
})
const scopeTitle = computed(() => {
  if (scopeParts.value.scope_type === 'factory') return '全厂默认'
  const workshop = activeWorkshops.value.find((item) => item.code === scopeParts.value.scope_key)
  return workshop ? `${workshop.name} (${workshop.code})` : scopeParts.value.scope_key
})
const hasOverrides = computed(() => ruleRows.value.some((item) => item.source === 'override'))
const ruleStats = computed(() => [
  { label: '规则总数', value: totalRuleCount.value, meta: '当前作用域', tone: 'normal' },
  { label: '覆盖数量', value: overrideCount.value, meta: '车间覆盖', tone: overrideCount.value ? 'warning' : 'normal' },
  { label: '默认继承', value: inheritedCount.value, meta: '沿用全厂', tone: 'success' },
  { label: '待保存变化', value: dirtyCount.value, meta: '本页编辑', tone: dirtyCount.value ? 'danger' : 'success' }
])

function hydrateRows(rows) {
  ruleRows.value = rows.map((item) => ({
    ...item,
    editValue: Number(item.value)
  }))
}

function precisionFor(row) {
  return row.value_type === 'int' ? 0 : 2
}

function stepFor(row) {
  return row.value_type === 'int' ? 1 : 0.5
}

function hasRuleChanged(row) {
  return Number(row.editValue) !== Number(row.value)
}

function ruleRowClassName({ row }) {
  return hasRuleChanged(row) ? 'is-dirty' : ''
}

async function loadWorkshops() {
  workshops.value = await fetchWorkshops({ limit: 500 })
}

async function loadRules() {
  loading.value = true
  try {
    const rows = await fetchRuleConfigs(scopeParts.value)
    hydrateRows(rows)
  } finally {
    loading.value = false
  }
}

async function saveRule(row) {
  savingKey.value = row.key
  try {
    const payload = { value: Number(row.editValue) }
    const saved = row.id
      ? await updateRuleConfig(row.id, payload)
      : await upsertRuleConfig({
        ...scopeParts.value,
        key: row.key,
        value: Number(row.editValue)
      })
    const index = ruleRows.value.findIndex((item) => item.key === row.key)
    if (index >= 0) {
      ruleRows.value[index] = {
        ...saved,
        editValue: Number(saved.value)
      }
    }
    ElMessage.success('规则已保存')
  } finally {
    savingKey.value = ''
  }
}

onMounted(async () => {
  await loadWorkshops()
  await loadRules()
})
</script>

<style scoped>
.rule-config-center {
  --rule-accent: #00f2ff;
  --rule-accent-strong: #74f5ff;
  --rule-bg: #06101f;
  --rule-card: rgba(6, 26, 49, 0.88);
  --rule-card-strong: rgba(8, 38, 66, 0.92);
  --rule-danger: #ff5b2e;
  --rule-line: rgba(0, 242, 255, 0.18);
  --rule-line-strong: rgba(0, 242, 255, 0.38);
  --rule-muted: rgba(185, 223, 235, 0.64);
  --rule-text: rgba(225, 253, 255, 0.92);
  --rule-warning: #ffab00;
  position: relative;
  display: grid;
  gap: 16px;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: var(--rule-text);
}

.rule-config-center::before {
  position: absolute;
  inset: 72px 0 auto;
  height: 280px;
  opacity: 0.34;
  background:
    radial-gradient(circle at 8% 18%, rgba(0, 242, 255, 0.2), transparent 28%),
    linear-gradient(rgba(0, 242, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.06) 1px, transparent 1px);
  background-size: auto, 32px 32px, 32px 32px;
  content: "";
  pointer-events: none;
}

.rule-config-center > * {
  position: relative;
}

.rule-config-center__hero,
.rule-config-center__stat,
.rule-config-center__cabin,
.rule-surface,
.rule-config-center__rail {
  border: 1px solid var(--rule-line);
  background:
    linear-gradient(180deg, rgba(9, 37, 63, 0.92), rgba(2, 14, 29, 0.94)),
    rgba(1, 16, 31, 0.84);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 18px 46px rgba(0, 18, 42, 0.22);
}

.rule-config-center__hero {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  overflow: hidden;
  border-radius: 18px;
  padding: 20px;
}

.rule-config-center__hero::after {
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.72), transparent);
  animation: ruleEnergyLine 5s linear infinite;
  content: "";
}

.rule-config-center__eyebrow,
.rule-config-center__stat span,
.rule-config-center__stat small,
.rule-config-center__cabin-head span,
.rule-config-center__scope-card span,
.rule-config-center__health span,
.rule-surface__head span,
.rule-surface__state small,
.rule-key span,
.rule-config-center__rail span {
  color: rgba(116, 245, 255, 0.72);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.rule-config-center__title-block {
  min-width: 0;
}

.rule-config-center__title-block h1 {
  margin: 6px 0 0;
  color: #e1fdff;
  font-size: clamp(26px, 3vw, 40px);
  letter-spacing: -0.022em;
  line-height: 1.05;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.14);
}

.rule-config-center__hero-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.rule-config-center__refresh {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.34);
  background: rgba(0, 242, 255, 0.1);
  color: #e1fdff;
}

.rule-config-center__refresh::after,
.rule-save::after {
  position: absolute;
  inset: -60% 0 auto;
  height: 48%;
  background: linear-gradient(180deg, transparent, rgba(116, 245, 255, 0.38), transparent);
  content: "";
  opacity: 0;
  transform: translateY(-100%);
  transition:
    opacity var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-normal) var(--xt-ease);
}

@media (hover: hover) {
  .rule-config-center__refresh:hover::after,
  .rule-save:hover::after {
    opacity: 1;
    transform: translateY(360%);
  }
}

.rule-config-center__status {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  animation: rulePanelIn 380ms var(--xt-ease) both;
}

.rule-config-center__stat {
  min-height: 112px;
  display: grid;
  align-content: space-between;
  border-radius: 16px;
  padding: 16px;
  overflow: hidden;
}

.rule-config-center__stat strong {
  color: #e1fdff;
  font-size: clamp(30px, 3.2vw, 44px);
  font-variant-numeric: tabular-nums;
  font-weight: 900;
  letter-spacing: -0.022em;
  line-height: 1;
}

.rule-config-center__stat.is-warning strong {
  color: var(--rule-warning);
}

.rule-config-center__stat.is-danger strong {
  color: var(--rule-danger);
}

.rule-config-center__stat.is-success strong {
  color: var(--rule-accent-strong);
}

.rule-config-center__layout {
  display: grid;
  grid-template-columns: minmax(230px, 280px) minmax(0, 1fr);
  gap: 16px;
  animation: rulePanelIn 420ms var(--xt-ease) 80ms both;
}

.rule-config-center__cabin,
.rule-surface {
  border-radius: 18px;
  overflow: hidden;
}

.rule-config-center__cabin {
  display: grid;
  align-content: start;
  gap: 16px;
  padding: 18px;
}

.rule-config-center__cabin-head,
.rule-surface__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.rule-config-center__cabin-head strong,
.rule-surface__head strong,
.rule-config-center__scope-card strong,
.rule-config-center__rail strong {
  display: block;
  margin-top: 4px;
  color: #e1fdff;
  font-size: 18px;
  font-weight: 900;
  letter-spacing: -0.012em;
}

.rule-config-center__scope-select {
  width: 100%;
}

.rule-config-center__scope-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--rule-line-strong);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(0, 242, 255, 0.16), rgba(0, 242, 255, 0.03)),
    rgba(1, 16, 31, 0.76);
  box-shadow: 0 0 30px rgba(0, 242, 255, 0.1);
}

.rule-config-center__health {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.rule-config-center__health div {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 12px;
  background: rgba(1, 16, 31, 0.66);
}

.rule-config-center__health strong {
  color: #e1fdff;
  font-size: 24px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.rule-surface__head {
  padding: 18px 20px;
  border-bottom: 1px solid var(--rule-line);
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.12), transparent 54%),
    rgba(1, 16, 31, 0.58);
}

.rule-surface__state {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rule-table {
  --el-bg-color: rgba(2, 14, 29, 0.94);
  --el-fill-color-blank: rgba(2, 14, 29, 0.94);
  --el-table-bg-color: transparent;
  --el-table-border-color: rgba(0, 242, 255, 0.1);
  --el-table-current-row-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-expanded-cell-bg-color: transparent;
  --el-table-header-bg-color: rgba(2, 14, 29, 0.94);
  --el-table-header-text-color: rgba(116, 245, 255, 0.82);
  --el-table-row-hover-bg-color: rgba(0, 242, 255, 0.07);
  --el-table-tr-bg-color: rgba(1, 16, 31, 0.58);
  --el-table-text-color: rgba(225, 253, 255, 0.86);
  width: 100%;
  background: rgba(1, 16, 31, 0.58);
}

.rule-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.rule-table :deep(.el-table__body-wrapper),
.rule-table :deep(.el-table__body),
.rule-table :deep(.el-scrollbar__view),
.rule-table :deep(tr.el-table__row) {
  background: rgba(1, 16, 31, 0.58);
}

.rule-table :deep(th.el-table__cell) {
  border-bottom: 1px solid var(--rule-line);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.08em;
}

.rule-table :deep(td.el-table__cell) {
  border-bottom: 1px solid rgba(0, 242, 255, 0.08);
  background: transparent;
}

.rule-table :deep(.el-table__row.is-dirty td.el-table__cell) {
  background:
    linear-gradient(90deg, rgba(255, 171, 0, 0.12), rgba(0, 242, 255, 0.04)),
    rgba(1, 16, 31, 0.42);
  animation: ruleDirtyPulse 2.4s var(--xt-ease) infinite;
}

.rule-key {
  display: grid;
  gap: 4px;
}

.rule-key strong,
.rule-value {
  color: #e1fdff;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.rule-value {
  color: var(--rule-accent-strong);
}

.rule-input {
  max-width: 160px;
}

.rule-input :deep(.el-input__wrapper),
.rule-config-center__scope-select :deep(.el-select__wrapper) {
  border-radius: 10px;
  background: rgba(1, 16, 31, 0.82);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.24),
    inset 0 0 0 1px var(--rule-line);
}

.rule-input :deep(.el-input__inner),
.rule-config-center__scope-select :deep(.el-select__placeholder),
.rule-config-center__scope-select :deep(.el-select__selected-item) {
  color: #e1fdff;
}

.rule-save {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.38);
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.22), rgba(0, 104, 153, 0.2)),
    rgba(1, 16, 31, 0.82);
  color: #e1fdff;
  box-shadow: 0 0 20px rgba(0, 242, 255, 0.1);
}

.rule-config-center__mobile-rules {
  display: none;
}

.rule-config-center__mobile-rule {
  display: grid;
  gap: 14px;
  padding: 16px;
  border-top: 1px solid rgba(0, 242, 255, 0.12);
  background: rgba(1, 16, 31, 0.58);
}

.rule-config-center__mobile-rule.is-dirty {
  background:
    linear-gradient(90deg, rgba(255, 171, 0, 0.12), rgba(0, 242, 255, 0.04)),
    rgba(1, 16, 31, 0.62);
}

.rule-config-center__mobile-rule header,
.rule-config-center__mobile-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rule-config-center__mobile-values div {
  display: grid;
  gap: 4px;
}

.rule-config-center__mobile-values span {
  color: rgba(116, 245, 255, 0.72);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.rule-config-center__mobile-values strong {
  color: var(--rule-accent-strong);
  font-size: 22px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.rule-config-center__rail {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 36px minmax(0, 1fr) 36px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  border-radius: 16px;
  padding: 16px;
  animation: rulePanelIn 420ms var(--xt-ease) 140ms both;
}

.rule-config-center__rail div {
  min-width: 0;
}

.rule-config-center__rail i {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--rule-accent), transparent);
  box-shadow: 0 0 14px rgba(0, 242, 255, 0.34);
}

.rule-config-center :deep(.reference-status) {
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: #74f5ff;
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.rule-config-center :deep(.reference-status[data-status="warning"]) {
  border-color: rgba(255, 171, 0, 0.3);
  background: rgba(255, 171, 0, 0.12);
  color: var(--rule-warning);
}

@keyframes rulePanelIn {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes ruleDirtyPulse {
  0%,
  100% {
    box-shadow: inset 0 0 0 rgba(255, 171, 0, 0);
  }

  50% {
    box-shadow: inset 0 0 22px rgba(255, 171, 0, 0.08);
  }
}

@keyframes ruleEnergyLine {
  0% { transform: translateX(-42%); opacity: 0.3; }
  50% { opacity: 1; }
  100% { transform: translateX(42%); opacity: 0.3; }
}

@media (max-width: 1100px) {
  .rule-config-center__status {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rule-config-center__layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .rule-config-center__hero,
  .rule-surface__head,
  .rule-surface__state {
    align-items: flex-start;
    flex-direction: column;
  }

  .rule-config-center__hero-actions,
  .rule-config-center__refresh {
    width: 100%;
  }

  .rule-config-center__status,
  .rule-config-center__health,
  .rule-config-center__rail {
    grid-template-columns: 1fr;
  }

  .rule-config-center__rail i {
    width: 1px;
    height: 24px;
    justify-self: start;
  }

  .rule-table {
    display: none;
  }

  .rule-config-center__mobile-rules {
    display: grid;
  }

  .rule-config-center__mobile-rule header,
  .rule-config-center__mobile-values {
    align-items: flex-start;
    flex-direction: column;
  }

  .rule-config-center__mobile-values .rule-input,
  .rule-config-center__mobile-rule .rule-save {
    width: 100%;
    max-width: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .rule-config-center__hero::after,
  .rule-config-center__status,
  .rule-config-center__layout,
  .rule-config-center__rail,
  .rule-table :deep(.el-table__row.is-dirty td.el-table__cell) {
    animation: none;
  }

  .rule-config-center__refresh::after,
  .rule-save::after {
    transition: none;
  }
}
</style>

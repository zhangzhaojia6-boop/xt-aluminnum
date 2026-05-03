<template>
  <ReferencePageFrame
    module-number="14"
    title="规则配置"
    :tags="['阈值', '车间覆盖', '自动校验']"
    data-testid="rule-config-page"
  >
    <template #actions>
      <el-select
        v-model="selectedScope"
        style="width: 260px"
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
      <el-button :loading="loading" data-testid="rule-config-refresh" @click="loadRules">刷新</el-button>
    </template>

    <section class="rule-surface">
      <div class="rule-surface__head">
        <div>
          <span>当前口径</span>
          <strong>{{ scopeTitle }}</strong>
        </div>
        <ReferenceStatusTag :status="hasOverrides ? 'warning' : 'success'" :label="hasOverrides ? '车间覆盖' : '继承默认'" />
      </div>

      <el-table
        v-loading="loading"
        :data="ruleRows"
        class="rule-table"
        row-key="key"
        data-testid="rule-config-table"
      >
        <el-table-column prop="key" label="规则键" min-width="250">
          <template #default="{ row }">
            <div class="rule-key">
              <strong>{{ row.key }}</strong>
              <span>{{ ruleLabels[row.key] || row.key }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前值" width="180" align="right">
          <template #default="{ row }">
            <span class="rule-value">{{ row.value }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="130">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.source === 'override' ? 'warning' : 'success'" :label="row.source === 'override' ? '覆盖' : '默认'" />
          </template>
        </el-table-column>
        <el-table-column label="调整" width="220" align="right">
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
        <el-table-column label="" width="110" align="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              :loading="savingKey === row.key"
              :disabled="Number(row.editValue) === Number(row.value)"
              data-testid="rule-config-save"
              @click="saveRule(row)"
            >
              保存
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
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
.rule-surface {
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-lg);
  box-shadow: var(--xt-shadow-sm);
  overflow: hidden;
}

.rule-surface__head {
  align-items: center;
  border-bottom: 1px solid var(--xt-border-light);
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
}

.rule-surface__head span,
.rule-key span {
  color: var(--xt-text-secondary);
  display: block;
  font-size: 12px;
  font-weight: 700;
}

.rule-surface__head strong {
  color: var(--xt-gray-900);
  display: block;
  font-size: 16px;
  margin-top: 4px;
}

.rule-table {
  width: 100%;
}

.rule-key {
  display: grid;
  gap: 4px;
}

.rule-key strong {
  color: var(--xt-gray-900);
  font-variant-numeric: tabular-nums;
}

.rule-value {
  color: var(--xt-gray-900);
  font-variant-numeric: tabular-nums;
  font-weight: 800;
}

.rule-input {
  max-width: 160px;
}

@media (max-width: 720px) {
  .rule-surface__head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

<template>
  <ReferencePageFrame
    module-number="10"
    title="成本核算与效益中心"
    :tags="['策略引擎', '吨耗口径', '校差记录']"
    class="review-cost-center-v2"
    data-testid="review-cost-center"
  >
    <template #actions>
      <el-date-picker v-model="businessDate" type="date" value-format="YYYY-MM-DD" />
      <el-select v-model="strategyCode" style="width: 280px" @change="resetTemplate">
        <el-option v-for="item in strategyOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="workshopCode" style="width: 160px">
        <el-option v-for="item in workshopOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-segmented v-model="caliber" :options="caliberOptions" />
      <el-button type="primary" @click="recalculate">重新计算</el-button>
    </template>

    <section class="cost-ledger" data-testid="cost-ledger">
      <article class="cost-ledger__card cost-ledger__card--primary">
        <span>收入估算</span>
        <strong>{{ ledgerSummary.revenue == null ? '--' : `¥ ${formatNumber(ledgerSummary.revenue, 2)}` }}</strong>
        <em>{{ ledgerSummary.revenuePerTon == null ? '未配置单价' : `单价 ${formatNumber(ledgerSummary.revenuePerTon, 2)}` }}</em>
      </article>
      <article class="cost-ledger__card">
        <span>成本估算</span>
        <strong>¥ {{ formatNumber(ledgerSummary.cost, 2) }}</strong>
        <em>经营口径</em>
      </article>
      <article class="cost-ledger__card" :class="{ 'is-loss': ledgerSummary.margin != null && ledgerSummary.margin < 0 }">
        <span>毛利估算</span>
        <strong>{{ ledgerSummary.margin == null ? '--' : `¥ ${formatNumber(ledgerSummary.margin, 2)}` }}</strong>
        <em>收入 - 成本</em>
      </article>
      <article class="cost-ledger__card">
        <span>每吨成本</span>
        <strong>¥ {{ formatNumber(ledgerSummary.perTon, 2) }}</strong>
        <em>{{ caliber === 'throughput' ? '按通货量' : '按产量' }}</em>
      </article>
      <article class="cost-ledger__card">
        <span>主要成本项</span>
        <strong>{{ ledgerSummary.majorCost?.label || '--' }}</strong>
        <em>{{ ledgerSummary.majorCost ? `¥ ${formatNumber(ledgerSummary.majorCost.value, 2)}` : '暂无' }}</em>
      </article>
    </section>

    <section class="cost-flow">
      <div>
        <span>产量</span>
        <strong>{{ formatNumber(ledgerSummary.outputTon, 2) }} 吨</strong>
      </div>
      <div>
        <span>通货量</span>
        <strong>{{ formatNumber(ledgerSummary.throughputTon, 2) }} 吨</strong>
      </div>
      <div>
        <span>损耗</span>
        <strong>{{ formatNumber(ledgerSummary.lossTon, 2) }} 吨</strong>
      </div>
      <div>
        <span>口径</span>
        <strong>{{ caliber === 'throughput' ? '按通货量' : '按产量' }}</strong>
      </div>
    </section>

    <el-card class="panel">
      <template #header>成本拆解</template>
      <el-table :data="result.breakdown || []" stripe size="small">
        <el-table-column prop="label" label="科目" min-width="120" />
        <el-table-column label="金额" min-width="110" align="right">
          <template #default="{ row }">¥ {{ formatNumber(row.value, 2) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="panel">
      <template #header>工序拆解</template>
      <el-table class="process-table" :data="result.processRows || []" stripe size="small">
        <el-table-column prop="process" label="工序" min-width="120" />
        <el-table-column prop="outputTon" label="产量(吨)" min-width="90" align="right" />
        <el-table-column label="成本(元)" min-width="110" align="right">
          <template #default="{ row }">¥ {{ formatNumber(row.cost, 2) }}</template>
        </el-table-column>
        <el-table-column label="吨耗(元/吨)" min-width="110" align="right">
          <template #default="{ row }">
            {{
              formatNumber(
                caliber === 'throughput'
                  ? (row.perTonByThroughput ?? result.byThroughputTon)
                  : (row.perTon ?? row.perTonByOutput ?? result.byOutputTon),
                2
              )
            }}
          </template>
        </el-table-column>
      </el-table>
      <div class="process-mobile-list">
        <article v-for="row in result.processRows || []" :key="row.process" class="process-mobile-row">
          <strong>{{ row.process }}</strong>
          <span>产量 {{ formatNumber(row.outputTon, 2) }} 吨</span>
          <span>成本 ¥ {{ formatNumber(row.cost, 2) }}</span>
          <span>
            吨耗 ¥ {{
              formatNumber(
                caliber === 'throughput'
                  ? (row.perTonByThroughput ?? result.byThroughputTon)
                  : (row.perTon ?? row.perTonByOutput ?? result.byOutputTon),
                2
              )
            }}
          </span>
        </article>
      </div>
    </el-card>

    <el-collapse class="cost-advanced">
      <el-collapse-item title="高级参数" name="advanced">
        <section class="review-cost-center-v2__grid">
          <el-card class="panel">
            <template #header>策略参数（可编辑 JSON）</template>
            <el-input v-model="scenarioJson" type="textarea" :rows="14" />
            <div class="header-actions" style="margin-top: 12px;">
              <el-button plain @click="resetTemplate">重置模板</el-button>
              <el-button type="primary" @click="recalculate">应用参数</el-button>
            </div>
          </el-card>

          <el-card class="panel">
            <template #header>后端表模型快照</template>
            <el-table :data="tableSnapshotRows" stripe size="small">
              <el-table-column prop="table" label="表名" min-width="190" />
              <el-table-column prop="rows" label="行数" width="90" align="right" />
              <el-table-column prop="status" label="状态" width="120" />
            </el-table>
          </el-card>
        </section>

        <section class="review-cost-center-v2__grid">
          <el-card class="panel">
            <template #header>校差记录</template>
            <el-table :data="result.varianceRecords || []" stripe size="small">
              <el-table-column prop="variance_type" label="类型" min-width="180" />
              <el-table-column prop="diff_value" label="差值" width="110" align="right" />
              <el-table-column prop="status" label="状态" width="110" />
            </el-table>
            <div v-if="!(result.varianceRecords || []).length" class="template-empty">暂无校差记录</div>
          </el-card>

          <el-card class="panel">
            <template #header>价格快照</template>
            <el-table :data="result.priceRows || []" stripe size="small" max-height="300">
              <el-table-column prop="code" label="价格编码" min-width="220" />
              <el-table-column prop="item_name" label="名称" min-width="160" />
              <el-table-column prop="unit" label="单位" width="90" />
              <el-table-column prop="workshop_scope" label="适用范围" min-width="130" />
              <el-table-column label="单价" min-width="130" align="right">
                <template #default="{ row }">¥ {{ formatNumber(row.unitPrice, 4) }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </section>
      </el-collapse-item>
    </el-collapse>
  </ReferencePageFrame>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { COST_STRATEGIES, COST_TABLE_KEYS, evaluateCostScenario } from '../../services/costing/engine.ts'
import { formatNumber } from '../../utils/display'

const strategyOptions = [
  { value: COST_STRATEGIES.CASTING_MACHINE_LABOR_SPLIT, label: '铸造策略（铸二/铸三）' },
  { value: COST_STRATEGIES.FINISHING_PARALLEL_PROCESS, label: '精整并行工序策略' },
  { value: COST_STRATEGIES.HOT_ROLLING_SHIFT_DAILY, label: '热轧班次日核算策略' },
  { value: COST_STRATEGIES.TENSION_LEVELING_MAIN_PLUS_AUX, label: '拉矫主线+公辅策略' },
  { value: COST_STRATEGIES.LOSS_DUAL_CALIBER, label: '损耗双口径策略（2050/1650/1850/花纹）' }
]

const workshopOptions = [
  { value: 'ZR2', label: '铸二' },
  { value: 'ZR3', label: '铸三' },
  { value: 'JZ', label: '精整' },
  { value: 'HR', label: '热轧' },
  { value: 'LJ', label: '拉矫' },
  { value: '2050', label: '2050' },
  { value: '1650', label: '1650' },
  { value: '1850', label: '1850' },
  { value: 'HWB', label: '花纹板' }
]

const caliberOptions = [
  { value: 'output', label: '按产量' },
  { value: 'throughput', label: '按通货量' }
]

const businessDate = ref(dayjs().format('YYYY-MM-DD'))
const strategyCode = ref(COST_STRATEGIES.CASTING_MACHINE_LABOR_SPLIT)
const workshopCode = ref('ZR2')
const caliber = ref('output')
const scenarioJson = ref('')
const result = ref({
  totalCost: 0,
  byOutputTon: 0,
  byThroughputTon: 0,
  breakdown: [],
  processRows: [],
  priceRows: [],
  explanation: [],
  tableModels: {},
  varianceRecords: []
})

function parseScenarioPayload() {
  try {
    return JSON.parse(scenarioJson.value || '{}')
  } catch {
    return {}
  }
}

function sumOutputTon(rows = []) {
  return rows.reduce((sum, row) => sum + Number(row.outputTon || 0), 0)
}

const ledgerSummary = computed(() => {
  const scenario = parseScenarioPayload()
  const processOutput = sumOutputTon(result.value.processRows || [])
  const outputTon = Number(scenario.outputTon || processOutput || 0)
  const throughputTon = Number(scenario.throughputTon || outputTon || 0)
  const lossTon = Math.max(throughputTon - outputTon, 0)
  const revenuePerTon = Number.isFinite(Number(scenario.revenuePerTon)) && Number(scenario.revenuePerTon) > 0
    ? Number(scenario.revenuePerTon)
    : null
  const revenue = revenuePerTon == null ? null : outputTon * revenuePerTon
  const cost = Number(result.value.totalCost || 0)
  const margin = revenue === null ? null : revenue - cost
  const perTon = caliber.value === 'throughput'
    ? result.value.byThroughputTon
    : result.value.byOutputTon

  return {
    outputTon,
    throughputTon,
    lossTon,
    revenue,
    revenuePerTon,
    cost,
    margin,
    perTon,
    majorCost: [...(result.value.breakdown || [])].sort((a, b) => Number(b.value || 0) - Number(a.value || 0))[0] || null,
  }
})

function buildDefaultScenario(code) {
  if (code === COST_STRATEGIES.CASTING_MACHINE_LABOR_SPLIT) {
    return {
      outputTon: 230,
      throughputTon: 245,
      electricityKwh: 8200,
      gasM3: 1600,
      laborTotal: 14800,
      directItems: [{ code: 'D40', quantity: 120 }],
      alloyItems: [{ code: 'ALLOY_A', amount: 26000 }]
    }
  }
  if (code === COST_STRATEGIES.FINISHING_PARALLEL_PROCESS) {
    return {
      throughputTon: 520,
      processes: [
        { name: '新19辊', outputTon: 220, laborCost: 6200, electricityKwh: 3800, packagingAmount: 1200, items: [{ code: 'D40', quantity: 18 }] },
        { name: '纵剪', outputTon: 170, laborCost: 4200, electricityKwh: 2600, packagingAmount: 1500, items: [{ code: 'D40', quantity: 10 }] },
        { name: '包装', outputTon: 130, laborCost: 3600, electricityKwh: 1200, packagingAmount: 5600, items: [{ code: 'PACK_MISC', amount: 1900 }] }
      ]
    }
  }
  if (code === COST_STRATEGIES.HOT_ROLLING_SHIFT_DAILY) {
    return {
      throughputTon: 435,
      shifts: [
        { name: '白班', outputTon: 152.1, laborCount: 26, electricityKwh: 12100, gasM3: 580, waterTon: 90, supportAmount: 1800, items: [{ code: 'ROLLING_OIL', quantity: 95 }] },
        { name: '小夜', outputTon: 138.45, laborCount: 24, electricityKwh: 10800, gasM3: 530, waterTon: 88, supportAmount: 1700, items: [{ code: 'ROLLING_OIL', quantity: 88 }] },
        { name: '大夜', outputTon: 120.38, laborCount: 23, electricityKwh: 9900, gasM3: 505, waterTon: 86, supportAmount: 1650, items: [{ code: 'ROLLING_OIL', quantity: 81 }] }
      ]
    }
  }
  if (code === COST_STRATEGIES.TENSION_LEVELING_MAIN_PLUS_AUX) {
    return {
      throughputTon: 410,
      airCompressorKwh: 2400,
      boilerGasM3: 620,
      processes: [
        { key: 'anneal', name: '退火炉', outputTon: 120, electricityKwh: 4200, gasM3: 900, laborCost: 3200, items: [{ code: 'THERMOCOUPLE', quantity: 55 }] },
        { key: 'leveling', name: '拉矫', outputTon: 140, electricityKwh: 3100, waterTon: 150, laborCost: 3600, items: [{ code: 'ALUMINUM_SLEEVE', quantity: 38 }, { code: 'D40', quantity: 22 }] },
        { key: 'slitting', name: '大分切', outputTon: 88, electricityKwh: 1800, laborCost: 2300, items: [{ code: 'STEEL_BELT', quantity: 48 }, { code: 'STEEL_BUCKLE', quantity: 16 }] },
        { key: 'pack', name: '包装', outputTon: 62, electricityKwh: 900, laborCost: 1900, items: [{ code: 'PACK_MISC', amount: 2400 }] }
      ]
    }
  }
  return {
    workshopCode: '2050',
    outputTon: 360,
    throughputTon: 420,
    electricityKwh: 12600,
    supportAmount: 5200,
    patternExtraAmount: 0,
    lossItems: [
      { code: 'ROLLING_OIL', quantity: 210 },
      { code: 'WHITE_SOIL', quantity: 32 },
      { code: 'DIATOMITE', quantity: 18 },
      { code: 'ROLLER_GUARANTEE', quantity: 1 }
    ],
    roleLaborRows: [
      { role: '主操', passes: 56, minutes: 410 },
      { role: '副操', passes: 56, minutes: 410 },
      { role: '普工', passes: 56, minutes: 410 },
      { role: '行车工', passes: 56, minutes: 410 }
    ]
  }
}

function resetTemplate() {
  const payload = buildDefaultScenario(strategyCode.value)
  scenarioJson.value = JSON.stringify(payload, null, 2)
  recalculate()
}

function recalculate() {
  try {
    const scenario = JSON.parse(scenarioJson.value || '{}')
    const computedResult = evaluateCostScenario({
      ...scenario,
      strategyCode: strategyCode.value,
      workshopCode: workshopCode.value,
      businessDate: businessDate.value,
      caliber: caliber.value
    })
    result.value = computedResult
  } catch (error) {
    ElMessage.error(error?.message || '策略参数解析失败')
  }
}

const tableSnapshotRows = computed(() => {
  const models = result.value.tableModels || {}
  return [
    COST_TABLE_KEYS.PRICE_MASTER,
    COST_TABLE_KEYS.WORKSHOP_STRATEGY,
    COST_TABLE_KEYS.DAILY_RESULT,
    COST_TABLE_KEYS.MONTHLY_ROLLUP,
    COST_TABLE_KEYS.VARIANCE_RECORD
  ].map((table) => {
    const rows = Array.isArray(models[table]) ? models[table] : []
    return {
      table,
      rows: rows.length,
      status: rows.length > 0 ? '已生成' : '待生成'
    }
  })
})

resetTemplate()
</script>

<style scoped>
.review-cost-center-v2__header {
  display: grid;
  gap: 10px;
}

.review-cost-center-v2__header h1 {
  margin: 0;
}

.review-cost-center-v2__header p {
  margin: 6px 0 0;
  color: var(--app-muted);
}

.review-cost-center-v2__grid {
  display: grid;
  gap: 12px;
  grid-template-columns: 1.1fr 0.9fr;
}

.review-cost-center-v2__list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.review-cost-center-v2 {
  min-width: 0;
  max-width: 100%;
}

.review-cost-center-v2 :deep(.reference-page__header),
.review-cost-center-v2 :deep(.reference-page__body) {
  min-width: 0;
  max-width: 100%;
}

.review-cost-center-v2 :deep(.reference-page__header) {
  display: grid;
  align-items: start;
}

.review-cost-center-v2 :deep(.reference-page__title-group) {
  width: 100%;
  grid-template-columns: auto minmax(0, 1fr);
}

.review-cost-center-v2 :deep(.reference-page__tags) {
  grid-column: 1 / -1;
}

.review-cost-center-v2 :deep(.reference-page__actions) {
  width: 100%;
  justify-content: start;
  flex-wrap: wrap;
}

.cost-ledger {
  display: grid;
  grid-template-columns: minmax(220px, 1.25fr) repeat(4, minmax(150px, 1fr));
  gap: 12px;
}

.cost-ledger__card {
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 16px;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.cost-ledger__card--primary {
  border-color: transparent;
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
}

.cost-ledger__card span,
.cost-flow span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.cost-ledger__card--primary span,
.cost-ledger__card--primary em,
.cost-ledger__card--primary strong {
  color: rgba(255, 255, 255, 0.92);
}

.cost-ledger__card strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 26px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.cost-ledger__card em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.cost-ledger__card.is-loss {
  border-color: rgba(194, 65, 52, 0.24);
}

.cost-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
}

.cost-flow div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 6px;
  background: var(--xt-bg-panel-soft);
}

.cost-flow strong {
  color: var(--xt-text);
  font-weight: 900;
}

.process-mobile-list {
  display: none;
}

.cost-advanced {
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
  overflow: hidden;
}

.cost-advanced :deep(.el-collapse-item__header) {
  padding: 0 16px;
  border-bottom-color: var(--xt-border-light);
  font-weight: 900;
}

.cost-advanced :deep(.el-collapse-item__content) {
  display: grid;
  gap: 12px;
  padding: 12px;
}

@media (max-width: 1024px) {
  .review-cost-center-v2__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1100px) {
  .review-cost-center-v2 :deep(.reference-page__actions) {
    display: flex;
    flex-wrap: wrap;
    min-width: 0;
    max-width: 100%;
  }

  .review-cost-center-v2 :deep(.reference-page__actions .el-select) {
    width: min(100%, 220px) !important;
  }

  .cost-ledger {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cost-flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .review-cost-center-v2 :deep(.reference-page__actions) {
    display: grid;
    grid-template-columns: 1fr;
    width: 100%;
  }

  .review-cost-center-v2 :deep(.reference-page__actions .el-date-editor),
  .review-cost-center-v2 :deep(.reference-page__actions .el-select),
  .review-cost-center-v2 :deep(.reference-page__actions .el-segmented),
  .review-cost-center-v2 :deep(.reference-page__actions .el-button) {
    width: 100% !important;
  }

  .cost-ledger,
  .cost-flow {
    grid-template-columns: 1fr;
  }

  .process-table {
    display: none;
  }

  .process-mobile-list {
    display: grid;
    gap: 10px;
  }

  .process-mobile-row {
    display: grid;
    gap: 6px;
    padding: 12px;
    border: 1px solid var(--xt-border-light);
    border-radius: 8px;
    background: var(--xt-bg-panel-soft);
  }

  .process-mobile-row strong {
    color: var(--xt-text);
    font-weight: 900;
  }

  .process-mobile-row span {
    color: var(--xt-text-secondary);
    font-size: 12px;
    font-weight: 800;
  }
}
</style>

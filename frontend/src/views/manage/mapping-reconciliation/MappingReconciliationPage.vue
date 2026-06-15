<template>
  <section class="xt-mapping-reconciliation" data-testid="mapping-reconciliation-page">
    <header class="xt-mapping-reconciliation__hero">
      <div>
        <span>只读 dry-run</span>
        <h1>输出skill 对齐</h1>
      </div>
      <button type="button" :disabled="running" @click="runDryRun">
        {{ running ? '试算中' : '运行真实试算' }}
      </button>
    </header>

    <div v-if="loading" class="xt-mapping-reconciliation__state">读取数据源</div>
    <div v-else-if="errorText" class="xt-mapping-reconciliation__state is-error">
      <span>{{ errorText }}</span>
      <button type="button" @click="loadSources">重试</button>
    </div>

    <section class="xt-mapping-reconciliation__metrics">
      <article v-for="card in metricCards" :key="card.key">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.meta }}</small>
      </article>
    </section>

    <section class="xt-mapping-reconciliation__grid">
      <article class="xt-mapping-reconciliation__panel is-controls">
        <header>
          <h2>试算条件</h2>
          <span>只读执行</span>
        </header>
        <div class="xt-mapping-reconciliation__controls">
          <label>
            <span>参考文件</span>
            <select v-model="selectedReferenceFile">
              <option value="">请选择文件</option>
              <option v-for="item in runnableFiles" :key="item.relative_path" :value="item.relative_path">
                {{ item.relative_path }}
              </option>
            </select>
          </label>
          <label>
            <span>业务日</span>
            <input v-model="businessDate" type="date" />
          </label>
          <fieldset>
            <legend>可比维度</legend>
            <label v-for="item in dimensionOptions" :key="item.key">
              <input v-model="selectedDimensions" type="checkbox" :value="item.key" />
              <span>{{ item.label }}</span>
            </label>
          </fieldset>
        </div>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>参考源</h2>
          <span>{{ sourceFiles.length }} 个文件</span>
        </header>
        <p class="xt-mapping-reconciliation__path">{{ sourceRoot }}</p>
        <div v-if="sourceFiles.length === 0" class="xt-mapping-reconciliation__empty">暂无可读文件</div>
        <ul v-else class="xt-mapping-reconciliation__file-list">
          <li v-for="item in sourceFiles.slice(0, 12)" :key="item.relative_path">
            <b>{{ item.name }}</b>
            <span>{{ item.extension || '无扩展名' }} / {{ formatBytes(item.size_bytes) }}</span>
          </li>
        </ul>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>系统源</h2>
          <span>{{ systemSources.length }} 张表</span>
        </header>
        <div class="xt-mapping-reconciliation__chips">
          <span v-for="item in systemSources" :key="item">{{ item }}</span>
        </div>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>差异原因汇总</h2>
          <span>{{ displayNumber(differenceSummary.total) }} 条</span>
        </header>
        <div v-if="!result" class="xt-mapping-reconciliation__empty">未运行试算</div>
        <div v-else-if="reasonBreakdown.length === 0" class="xt-mapping-reconciliation__empty">暂无差异原因</div>
        <ul v-else class="xt-mapping-reconciliation__summary">
          <li v-for="reason in reasonBreakdown" :key="reason.reason_code">
            <b>{{ reason.label }}</b>
            <strong>{{ displayNumber(reason.count) }}</strong>
          </li>
        </ul>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>字段匹配率</h2>
          <span>可比字段 {{ displayNumber(matchSummary.total_fields) }} 项</span>
        </header>
        <div v-if="!result" class="xt-mapping-reconciliation__empty">未运行试算</div>
        <div v-else-if="fieldBreakdown.length === 0" class="xt-mapping-reconciliation__empty">暂无字段结果</div>
        <ul v-else class="xt-mapping-reconciliation__field-rates">
          <li v-for="item in fieldBreakdown" :key="item.metric">
            <b>{{ metricLabel(item.metric) }}</b>
            <span>{{ displayNumber(item.match_rate) }}%</span>
          </li>
        </ul>
      </article>

      <article class="xt-mapping-reconciliation__panel is-wide">
        <header>
          <h2>差异明细</h2>
          <span>{{ differences.length }} 条</span>
        </header>
        <div v-if="differences.length === 0" class="xt-mapping-reconciliation__empty">当前没有差异</div>
        <div v-else class="xt-mapping-reconciliation__table-wrap">
          <table>
            <thead>
              <tr>
                <th>指标</th>
                <th>维度</th>
                <th>参考值</th>
                <th>系统值</th>
                <th>差异</th>
                <th>原因</th>
                <th>建议规则</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in differences" :key="`${item.reason_code}-${index}`">
                <td>{{ metricLabel(item.metric) }}</td>
                <td>{{ formatDimension(item.dimension) }}</td>
                <td>{{ formatValue(item.reference_value) }}</td>
                <td>{{ formatValue(item.system_value) }}</td>
                <td>{{ formatValue(item.diff_value) }}</td>
                <td>{{ reasonLabel(item.reason_code) }}</td>
                <td>{{ item.suggested_rule || '人工确认' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>规则建议</h2>
          <span>{{ ruleProposals.length }} 条</span>
        </header>
        <div v-if="ruleProposals.length === 0" class="xt-mapping-reconciliation__empty">暂无建议</div>
        <ol v-else class="xt-mapping-reconciliation__rules">
          <li v-for="item in ruleProposals" :key="`${item.field}-${item.reference_value}-${item.system_value}`">
            <b>{{ fieldLabel(item.field) }}</b>
            <span>{{ item.system_value }} → {{ item.reference_value }}</span>
            <small>{{ item.dry_run ? '仅试算' : '待确认' }}</small>
          </li>
        </ol>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchMappingReconciliationSources, runMappingReconciliation } from '../../../api/mapping-reconciliation.js'
import { inferLastCompletedBusinessDate } from '../../../utils/shiftClock.js'

const loading = ref(false)
const running = ref(false)
const errorText = ref('')
const sources = ref({ available: false, files: [], system_sources: [] })
const result = ref(null)
const selectedReferenceFile = ref('')
const businessDate = ref(inferLastCompletedBusinessDate())
const selectedDimensions = ref(['business_date', 'workshop'])

const sourceFiles = computed(() => sources.value?.files || [])
const runnableFiles = computed(() => sourceFiles.value.filter((item) => ['.txt', '.md', '.log', '.xlsx', '.xls', '.json', '.ndjson'].includes(item.extension)))
const systemSources = computed(() => sources.value?.system_sources || [])
const sourceRoot = computed(() => sources.value?.reference_source || '未配置')
const differences = computed(() => result.value?.differences || [])
const ruleProposals = computed(() => result.value?.rule_proposals || [])
const differenceSummary = computed(() => result.value?.difference_summary || { total: differences.value.length, by_reason_code: {}, by_metric: {}, reason_breakdown: [] })
const reasonBreakdown = computed(() => differenceSummary.value.reason_breakdown || [])
const matchRate = computed(() => Number(result.value?.overall_match_rate || 0))
const matchSummary = computed(() => result.value?.match_summary || {
  total_fields: Number(result.value?.total_fields || 0),
  matched_fields: Number(result.value?.matched_fields || 0),
  unmatched_fields: Math.max(Number(result.value?.total_fields || 0) - Number(result.value?.matched_fields || 0), 0),
  overall_match_rate: matchRate.value,
  field_breakdown: Object.entries(result.value?.field_match_rates || {}).map(([metric, match_rate]) => ({ metric, match_rate }))
})
const fieldBreakdown = computed(() => matchSummary.value.field_breakdown || [])
const referenceRowsCount = computed(() => Number(result.value?.reference_rows_count || 0))
const systemRowsCount = computed(() => Number(result.value?.system_rows_count || 0))
const runId = computed(() => result.value?.run_id || null)

const dimensionOptions = [
  { key: 'business_date', label: '日期' },
  { key: 'workshop', label: '车间' },
  { key: 'shift', label: '班次' },
  { key: 'machine', label: '机台' },
  { key: 'process', label: '工序' }
]

const defaultMappingFields = [
  {
    metric: 'input',
    reference_field: 'input_tons',
    system_field: 'input_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 15
  },
  {
    metric: 'output',
    reference_field: 'output_tons',
    system_field: 'output_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 30
  },
  {
    metric: 'scrap',
    reference_field: 'scrap_tons',
    system_field: 'scrap_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 10
  },
  {
    metric: 'downtime',
    reference_field: 'downtime_minutes',
    system_field: 'downtime_minutes',
    reference_unit: 'minute',
    system_unit: 'minute',
    tolerance: 1,
    weight: 10
  },
  {
    metric: 'quality',
    reference_field: 'quality_issue_count',
    system_field: 'quality_issue_count',
    reference_unit: 'count',
    system_unit: 'count',
    tolerance: 0,
    weight: 10
  },
  {
    metric: 'yield',
    reference_field: 'yield_rate',
    system_field: 'yield_rate',
    reference_unit: 'percent',
    system_unit: 'percent',
    tolerance: 0.01,
    weight: 15
  },
  {
    metric: 'energy',
    reference_field: 'energy_kwh',
    system_field: 'energy_kwh',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 15
  },
  {
    metric: 'gas',
    reference_field: 'gas_m3',
    system_field: 'gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 10
  },
  {
    metric: 'electricity_monthly',
    reference_field: 'electricity_monthly',
    system_field: 'electricity_monthly',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'electricity_target',
    reference_field: 'electricity_target',
    system_field: 'electricity_target',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'gas_monthly',
    reference_field: 'gas_monthly',
    system_field: 'gas_monthly',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'gas_target',
    reference_field: 'gas_target',
    system_field: 'gas_target',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'total_electricity',
    reference_field: 'total_electricity_kwh',
    system_field: 'total_electricity_kwh',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'new_plant_electricity',
    reference_field: 'new_plant_electricity_kwh',
    system_field: 'new_plant_electricity_kwh',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'park_electricity',
    reference_field: 'park_electricity_kwh',
    system_field: 'park_electricity_kwh',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'cast_roll_gas',
    reference_field: 'cast_roll_gas_m3',
    system_field: 'cast_roll_gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'smelting_gas',
    reference_field: 'smelting_gas_m3',
    system_field: 'smelting_gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'heating_furnace_gas',
    reference_field: 'heating_furnace_gas_m3',
    system_field: 'heating_furnace_gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'boiler_gas',
    reference_field: 'boiler_gas_m3',
    system_field: 'boiler_gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'total_gas',
    reference_field: 'total_gas_m3',
    system_field: 'total_gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'groundwater',
    reference_field: 'groundwater_ton',
    system_field: 'groundwater_ton',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'tap_water',
    reference_field: 'tap_water_ton',
    system_field: 'tap_water_ton',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.1,
    weight: 8
  },
  {
    metric: 'rolling_oil',
    reference_field: 'rolling_oil_per_ton',
    system_field: 'rolling_oil_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 10
  },
  {
    metric: 'liquefied_gas',
    reference_field: 'liquefied_gas_per_ton',
    system_field: 'liquefied_gas_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'titanium_wire',
    reference_field: 'titanium_wire_per_ton',
    system_field: 'titanium_wire_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'steel_strip',
    reference_field: 'steel_strip_per_ton',
    system_field: 'steel_strip_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'magnesium',
    reference_field: 'magnesium_per_ton',
    system_field: 'magnesium_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'manganese',
    reference_field: 'manganese_per_ton',
    system_field: 'manganese_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'iron',
    reference_field: 'iron_per_ton',
    system_field: 'iron_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'copper',
    reference_field: 'copper_per_ton',
    system_field: 'copper_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'hot_roll_emulsion',
    reference_field: 'hot_roll_emulsion_per_ton',
    system_field: 'hot_roll_emulsion_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'diatomite',
    reference_field: 'diatomite_per_ton',
    system_field: 'diatomite_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'white_earth',
    reference_field: 'white_earth_per_ton',
    system_field: 'white_earth_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'filter_cloth',
    reference_field: 'filter_cloth_daily',
    system_field: 'filter_cloth_daily',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'high_temp_tape',
    reference_field: 'high_temp_tape_daily',
    system_field: 'high_temp_tape_daily',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'regen_oil_out',
    reference_field: 'regen_oil_out',
    system_field: 'regen_oil_out',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'regen_oil_in',
    reference_field: 'regen_oil_in',
    system_field: 'regen_oil_in',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'hydraulic_oil_daily',
    reference_field: 'hydraulic_oil_daily',
    system_field: 'hydraulic_oil_daily',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'hydraulic_oil_monthly',
    reference_field: 'hydraulic_oil_monthly',
    system_field: 'hydraulic_oil_monthly',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'hydraulic_oil_target',
    reference_field: 'hydraulic_oil_target',
    system_field: 'hydraulic_oil_target',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'gear_oil_daily',
    reference_field: 'gear_oil_daily',
    system_field: 'gear_oil_daily',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'gear_oil_monthly',
    reference_field: 'gear_oil_monthly',
    system_field: 'gear_oil_monthly',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'gear_oil_target',
    reference_field: 'gear_oil_target',
    system_field: 'gear_oil_target',
    reference_unit: 'quantity',
    system_unit: 'quantity',
    tolerance: 0.01,
    weight: 6
  },
  {
    metric: 'd40',
    reference_field: 'd40_per_ton',
    system_field: 'd40_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'steel_plate',
    reference_field: 'steel_plate_per_ton',
    system_field: 'steel_plate_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'steel_buckle',
    reference_field: 'steel_buckle_per_ton',
    system_field: 'steel_buckle_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'filter_agent',
    reference_field: 'filter_agent_per_ton',
    system_field: 'filter_agent_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'paint',
    reference_field: 'paint_per_ton',
    system_field: 'paint_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'ingot_block',
    reference_field: 'ingot_block_count',
    system_field: 'ingot_block_count',
    reference_unit: 'count',
    system_unit: 'count',
    tolerance: 0,
    weight: 8
  },
  {
    metric: 'ingot_input',
    reference_field: 'ingot_input_tons',
    system_field: 'ingot_input_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'ingot_output',
    reference_field: 'ingot_output_tons',
    system_field: 'ingot_output_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'daily_contract',
    reference_field: 'daily_contract_weight',
    system_field: 'daily_contract_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'daily_hot_roll_contract',
    reference_field: 'daily_hot_roll_contract_weight',
    system_field: 'daily_hot_roll_contract_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'month_to_date_contract',
    reference_field: 'month_to_date_contract_weight',
    system_field: 'month_to_date_contract_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'remaining_contract',
    reference_field: 'remaining_contract_weight',
    system_field: 'remaining_contract_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'remaining_hot_roll_contract',
    reference_field: 'remaining_hot_roll_contract_weight',
    system_field: 'remaining_hot_roll_contract_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'remaining_contract_delta',
    reference_field: 'remaining_contract_delta_weight',
    system_field: 'remaining_contract_delta_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'billet_inventory',
    reference_field: 'billet_inventory_weight',
    system_field: 'billet_inventory_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'daily_input',
    reference_field: 'daily_input_weight',
    system_field: 'daily_input_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'month_to_date_input',
    reference_field: 'month_to_date_input_weight',
    system_field: 'month_to_date_input_weight',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'cost',
    reference_field: 'cost_per_ton',
    system_field: 'cost_per_ton',
    reference_unit: 'yuan_per_ton',
    system_unit: 'yuan_per_ton',
    tolerance: 0.01,
    weight: 10
  },
  {
    metric: 'total_cost',
    reference_field: 'total_cost',
    system_field: 'total_cost',
    reference_unit: 'yuan',
    system_unit: 'yuan',
    tolerance: 0.01,
    weight: 10
  },
  {
    metric: 'electricity_cost',
    reference_field: 'electricity_cost',
    system_field: 'electricity_cost',
    reference_unit: 'yuan',
    system_unit: 'yuan',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'natural_gas_cost',
    reference_field: 'natural_gas_cost',
    system_field: 'natural_gas_cost',
    reference_unit: 'yuan',
    system_unit: 'yuan',
    tolerance: 0.01,
    weight: 8
  },
  {
    metric: 'throughput_cost',
    reference_field: 'throughput_cost_per_ton',
    system_field: 'throughput_cost_per_ton',
    reference_unit: 'yuan_per_ton',
    system_unit: 'yuan_per_ton',
    tolerance: 0.01,
    weight: 10
  }
]

const defaultDimensionAliases = {
  workshop: {
    精整车间: '精整',
    拉矫车间: '拉矫',
    剪切车间: '园区剪切',
    成品库: '成品库'
  },
  shift: {
    白班: '长白班',
    小夜: '小夜班',
    大夜: '大夜班'
  }
}

const metricCards = computed(() => [
  { key: 'files', label: '参考文件', value: displayNumber(sourceFiles.value.length), meta: sources.value?.available ? '已挂载' : '未挂载' },
  { key: 'rows', label: '对齐行数', value: `${displayNumber(referenceRowsCount.value)} / ${displayNumber(systemRowsCount.value)}`, meta: '输出skill / 系统' },
  { key: 'match', label: '当前匹配率', value: `${displayNumber(matchRate.value)}%`, meta: result.value ? '来自试算' : '未运行' },
  { key: 'field-match', label: '字段匹配', value: `${displayNumber(matchSummary.value.matched_fields)} / ${displayNumber(matchSummary.value.total_fields)}`, meta: '已匹配 / 可比字段' },
  { key: 'field-miss', label: '未匹配字段', value: displayNumber(matchSummary.value.unmatched_fields), meta: '需要看差异原因' },
  { key: 'diff', label: '差异数量', value: displayNumber(differenceSummary.value.total), meta: '可追原因' },
  { key: 'run', label: '运行编号', value: runId.value ? `#${displayNumber(runId.value)}` : '-', meta: runId.value ? '可追溯' : '未保存' }
])

function displayNumber(value) {
  const number = Number(value || 0)
  return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
}

function formatBytes(value) {
  const number = Number(value || 0)
  if (number >= 1024 * 1024) return `${(number / 1024 / 1024).toFixed(1)} MB`
  if (number >= 1024) return `${(number / 1024).toFixed(1)} KB`
  return `${number} B`
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return displayNumber(value)
  return String(value)
}

function formatDimension(value) {
  if (!value) return '-'
  return Object.entries(value)
    .filter(([, item]) => item)
    .map(([key, item]) => `${fieldLabel(key)}:${item}`)
    .join(' / ')
}

function fieldLabel(value) {
  const labels = { business_date: '日期', workshop: '车间', shift: '班次', machine: '机台', process: '工序' }
  return labels[value] || value || '字段'
}

function metricLabel(value) {
  const labels = {
    input: '投入量',
    output: '产量',
    scrap: '废料',
    downtime: '停机',
    quality: '质量',
    yield: '成材率',
    energy: '能耗',
    gas: '燃气',
    electricity_monthly: '用电月累计',
    electricity_target: '用电指标',
    gas_monthly: '用气月累计',
    gas_target: '用气指标',
    total_electricity: '全厂用电',
    new_plant_electricity: '新厂用电',
    park_electricity: '园区用电',
    cast_roll_gas: '铸轧用气',
    smelting_gas: '熔炼炉用气',
    heating_furnace_gas: '加热炉用气',
    boiler_gas: '锅炉用气',
    total_gas: '天然气总量',
    groundwater: '地下水',
    tap_water: '自来水',
    electricity_cost: '电费',
    natural_gas_cost: '气费',
    rolling_oil: '轧制油吨耗',
    liquefied_gas: '液化气吨耗',
    titanium_wire: '钛丝吨耗',
    steel_strip: '钢带吨耗',
    magnesium: '镁吨耗',
    manganese: '锰吨耗',
    iron: '铁吨耗',
    copper: '铜吨耗',
    hot_roll_emulsion: '热轧乳液吨耗',
    diatomite: '硅藻土吨耗',
    white_earth: '白土吨耗',
    filter_cloth: '滤布日耗',
    high_temp_tape: '高温胶带日耗',
    regen_oil_out: '再生油出库',
    regen_oil_in: '再生油入库',
    hydraulic_oil_daily: '液压油日耗',
    hydraulic_oil_monthly: '液压油月累计',
    hydraulic_oil_target: '液压油指标',
    gear_oil_daily: '齿轮油日耗',
    gear_oil_monthly: '齿轮油月累计',
    gear_oil_target: '齿轮油指标',
    d40: 'D40吨耗',
    steel_plate: '钢板吨耗',
    steel_buckle: '钢扣吨耗',
    filter_agent: '飞滤剂吨耗',
    paint: '油漆吨耗',
    ingot_block: '铸锭块数',
    ingot_input: '铸锭投料量',
    ingot_output: '铸锭下机量',
    daily_contract: '当日接合同',
    daily_hot_roll_contract: '当日热轧合同',
    month_to_date_contract: '月累计合同',
    remaining_contract: '余合同量',
    remaining_hot_roll_contract: '余热轧合同',
    remaining_contract_delta: '余合同较昨日',
    billet_inventory: '坯料总量',
    daily_input: '当日投料',
    month_to_date_input: '月累计投料',
    cost: '吨成本',
    total_cost: '总成本',
    throughput_cost: '过站吨成本'
  }
  return labels[value] || value || '指标'
}

function reasonLabel(value) {
  const labels = {
    value_diff: '数值不一致',
    missing_system_row: '系统缺行',
    extra_system_row: '系统多行',
    missing_field_value: '字段缺值'
  }
  return labels[value] || value || '待确认'
}

async function loadSources() {
  loading.value = true
  errorText.value = ''
  try {
    sources.value = await fetchMappingReconciliationSources()
    if (!selectedReferenceFile.value && runnableFiles.value.length > 0) {
      selectedReferenceFile.value = runnableFiles.value[0].relative_path
    }
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '读取失败'
    sources.value = { available: false, files: [], system_sources: [] }
  } finally {
    loading.value = false
  }
}

async function runDryRun() {
  if (!selectedReferenceFile.value) {
    errorText.value = '请选择参考文件'
    return
  }
  if (!businessDate.value) {
    errorText.value = '请选择业务日'
    return
  }
  running.value = true
  errorText.value = ''
  try {
    result.value = await runMappingReconciliation({
      reference_file: selectedReferenceFile.value,
      business_date: businessDate.value,
      fields: defaultMappingFields,
      dimensions: selectedDimensions.value.length > 0 ? selectedDimensions.value : ['business_date', 'workshop'],
      dimension_aliases: defaultDimensionAliases
    })
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '试算失败'
  } finally {
    running.value = false
  }
}

onMounted(loadSources)
</script>

<style scoped>
.xt-mapping-reconciliation {
  --mapping-bg: #081116;
  --mapping-panel: #111b22;
  --mapping-border: rgba(179, 139, 69, 0.28);
  --mapping-gold: #c79b4b;
  --mapping-red: #7f1d1d;
  --mapping-text: #f5f0e6;
  display: grid;
  gap: var(--xt-space-4);
  min-height: calc(100vh - var(--xt-topbar-height) - var(--xt-space-10));
  color: var(--mapping-text);
}

.xt-mapping-reconciliation__hero,
.xt-mapping-reconciliation__metrics article,
.xt-mapping-reconciliation__panel,
.xt-mapping-reconciliation__state {
  border: 1px solid var(--mapping-border);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(199, 155, 75, 0.08), transparent 42%),
    linear-gradient(135deg, rgba(17, 27, 34, 0.96), rgba(8, 17, 22, 0.96));
  box-shadow: inset 0 1px 0 rgba(245, 240, 230, 0.06);
}

.xt-mapping-reconciliation__hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-4);
  min-height: 132px;
  padding: var(--xt-space-5);
}

.xt-mapping-reconciliation__hero span {
  color: var(--mapping-gold);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.16em;
}

.xt-mapping-reconciliation__hero h1 {
  margin: var(--xt-space-2) 0 0;
  color: var(--mapping-text);
  font-family: var(--xt-font-display);
  font-size: clamp(34px, 4vw, 56px);
  font-weight: 950;
  letter-spacing: -0.04em;
}

.xt-mapping-reconciliation button {
  min-height: 38px;
  padding: 0 var(--xt-space-4);
  border: 1px solid rgba(199, 155, 75, 0.42);
  border-radius: 999px;
  background: rgba(199, 155, 75, 0.12);
  color: var(--mapping-text);
  cursor: pointer;
  font-weight: 900;
}

.xt-mapping-reconciliation button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.xt-mapping-reconciliation__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--xt-space-3);
  min-height: 68px;
  color: rgba(245, 240, 230, 0.74);
  font-weight: 900;
}

.xt-mapping-reconciliation__state.is-error {
  border-color: rgba(127, 29, 29, 0.52);
  color: #ffb4a8;
}

.xt-mapping-reconciliation__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-mapping-reconciliation__metrics article {
  display: grid;
  gap: var(--xt-space-2);
  min-height: 120px;
  padding: var(--xt-space-4);
}

.xt-mapping-reconciliation__metrics span,
.xt-mapping-reconciliation__panel header span {
  color: rgba(245, 240, 230, 0.62);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.08em;
}

.xt-mapping-reconciliation__metrics strong {
  color: var(--mapping-gold);
  font-family: var(--xt-font-number);
  font-size: clamp(30px, 3vw, 44px);
  line-height: 1;
}

.xt-mapping-reconciliation__metrics small {
  color: rgba(245, 240, 230, 0.68);
  font-weight: 800;
}

.xt-mapping-reconciliation__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 0.7fr);
  gap: var(--xt-space-4);
}

.xt-mapping-reconciliation__panel {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
}

.xt-mapping-reconciliation__panel.is-wide {
  grid-column: 1 / -1;
}

.xt-mapping-reconciliation__panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding-bottom: var(--xt-space-3);
  border-bottom: 1px solid rgba(199, 155, 75, 0.18);
}

.xt-mapping-reconciliation__panel h2 {
  margin: 0;
  color: var(--mapping-text);
  font-size: var(--xt-text-lg);
  font-weight: 950;
}

.xt-mapping-reconciliation__path {
  overflow: hidden;
  margin: 0;
  color: rgba(245, 240, 230, 0.62);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-mapping-reconciliation__empty {
  min-height: 98px;
  display: grid;
  place-items: center;
  border: 1px dashed rgba(199, 155, 75, 0.28);
  border-radius: 12px;
  color: rgba(245, 240, 230, 0.54);
  font-weight: 900;
}

.xt-mapping-reconciliation__file-list,
.xt-mapping-reconciliation__rules,
.xt-mapping-reconciliation__summary,
.xt-mapping-reconciliation__field-rates {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-mapping-reconciliation__file-list li,
.xt-mapping-reconciliation__rules li,
.xt-mapping-reconciliation__summary li,
.xt-mapping-reconciliation__field-rates li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid rgba(199, 155, 75, 0.14);
  border-radius: 10px;
  background: rgba(245, 240, 230, 0.035);
}

.xt-mapping-reconciliation__file-list b,
.xt-mapping-reconciliation__rules b,
.xt-mapping-reconciliation__summary b,
.xt-mapping-reconciliation__field-rates b {
  overflow: hidden;
  color: var(--mapping-text);
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-mapping-reconciliation__file-list span,
.xt-mapping-reconciliation__rules span,
.xt-mapping-reconciliation__rules small {
  flex: 0 0 auto;
  color: rgba(245, 240, 230, 0.58);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-mapping-reconciliation__summary strong {
  color: var(--mapping-gold);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xl);
}

.xt-mapping-reconciliation__field-rates span {
  color: var(--mapping-gold);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 950;
}

.xt-mapping-reconciliation__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-2);
}

.xt-mapping-reconciliation__chips span {
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid rgba(199, 155, 75, 0.2);
  border-radius: 999px;
  background: rgba(199, 155, 75, 0.08);
  color: rgba(245, 240, 230, 0.78);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-mapping-reconciliation__panel.is-controls {
  grid-column: 1 / -1;
}

.xt-mapping-reconciliation__controls {
  display: grid;
  grid-template-columns: minmax(280px, 1.2fr) minmax(180px, 0.6fr) minmax(320px, 1fr);
  gap: var(--xt-space-3);
}

.xt-mapping-reconciliation__controls label,
.xt-mapping-reconciliation__controls fieldset {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
  min-width: 0;
  border: 0;
  padding: 0;
}

.xt-mapping-reconciliation__controls label span,
.xt-mapping-reconciliation__controls legend {
  color: rgba(245, 240, 230, 0.64);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-mapping-reconciliation__controls select,
.xt-mapping-reconciliation__controls input[type='date'] {
  width: 100%;
  min-height: 42px;
  border: 1px solid rgba(199, 155, 75, 0.28);
  border-radius: 10px;
  background: rgba(8, 17, 22, 0.72);
  color: var(--mapping-text);
  font-weight: 850;
  padding: 0 var(--xt-space-3);
}

.xt-mapping-reconciliation__controls fieldset {
  align-content: start;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.xt-mapping-reconciliation__controls fieldset legend {
  grid-column: 1 / -1;
}

.xt-mapping-reconciliation__controls fieldset label {
  display: flex;
  align-items: center;
  gap: var(--xt-space-1);
  color: rgba(245, 240, 230, 0.76);
  font-weight: 850;
}

.xt-mapping-reconciliation__table-wrap {
  overflow-x: auto;
}

.xt-mapping-reconciliation table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
}

.xt-mapping-reconciliation th,
.xt-mapping-reconciliation td {
  padding: 11px var(--xt-space-2);
  border-bottom: 1px solid rgba(199, 155, 75, 0.12);
  text-align: left;
}

.xt-mapping-reconciliation th {
  color: var(--mapping-gold);
  font-size: var(--xt-text-xs);
  font-weight: 950;
}

.xt-mapping-reconciliation td {
  color: rgba(245, 240, 230, 0.78);
  font-size: var(--xt-text-sm);
}

@media (max-width: 1120px) {
  .xt-mapping-reconciliation__metrics,
  .xt-mapping-reconciliation__grid,
  .xt-mapping-reconciliation__controls {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 760px) {
  .xt-mapping-reconciliation__hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .xt-mapping-reconciliation__metrics,
  .xt-mapping-reconciliation__grid,
  .xt-mapping-reconciliation__controls {
    grid-template-columns: 1fr;
  }

  .xt-mapping-reconciliation__controls fieldset {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

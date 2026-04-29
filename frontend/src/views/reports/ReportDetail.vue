<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>日报详情</h1>
        <p>查看结构化日报、文本摘要和归档版本，并支持导出。</p>
      </div>
      <div class="header-actions">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="download('json')">导出结构化数据</el-button>
        <el-button type="success" @click="download('csv')">导出逗号分隔表</el-button>
        <el-button type="warning" @click="download('xlsx')">导出电子表格</el-button>
      </div>
    </div>

    <div v-if="report" class="report-detail__field-stack">
      <XtFieldGroup title="结论区" tier="primary" :items="reportPrimaryFields" />
      <XtFieldGroup title="交付区" tier="supporting" :items="reportSupportingFields" />
      <XtFieldGroup title="审计区" tier="audit" :items="reportAuditFields" collapsed />
    </div>

    <el-card class="panel" v-if="report">
      <template #header>最终版文本日报</template>
      <div class="text-summary">{{ report.final_text_summary || '尚未生成最终版文本日报。' }}</div>
    </el-card>

    <el-card class="panel" v-if="report && !report.final_text_summary && report.text_summary">
      <template #header>文本摘要</template>
      <div class="text-summary">{{ report.text_summary || '当前未生成文本摘要内容。' }}</div>
    </el-card>

    <XtFieldGroup v-if="report" title="核心指标" tier="primary" :items="metricFields" />

    <el-card class="panel" v-if="yieldMatrixLane">
      <template #header>成品率矩阵正式口径</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="矩阵日期">{{ yieldMatrixLane.business_date ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="公司总成品率">{{ yieldMatrixLane.company_total_yield ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="M 指标">{{ yieldMatrixLane.mp_targets?.M ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="P 指标">{{ yieldMatrixLane.mp_targets?.P ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="快照数">{{ yieldMatrixLane.snapshot_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="质量状态">{{ yieldMatrixLane.quality_status ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="主交付范围">{{ yieldMatrixLane.primary_delivery_scope ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="交付范围">{{ yieldMatrixLane.delivery_scopes?.join(' / ') || '-' }}</el-descriptions-item>
      </el-descriptions>

      <ReferenceDataTable v-if="yieldMatrixWorkshopRows.length" :data="yieldMatrixWorkshopRows" stripe class="matrix-table">
        <el-table-column prop="workshop_key" label="矩阵口径" min-width="180" />
        <el-table-column prop="yield_rate" label="成品率" min-width="120" />
      </ReferenceDataTable>
    </el-card>

    <el-card class="panel" v-if="workshopRows.length">
      <template #header>车间汇总</template>
      <ReferenceDataTable :data="workshopRows" stripe>
        <el-table-column prop="workshop_name" label="车间" min-width="160" />
        <el-table-column prop="output_weight" label="产量" min-width="120" />
        <el-table-column prop="input_weight" label="投入" min-width="120" />
        <el-table-column prop="yield_rate" label="成材率" min-width="120" />
        <el-table-column prop="attendance_count" label="出勤" min-width="100" />
        <el-table-column prop="electricity_kwh" label="电耗" min-width="120" />
      </ReferenceDataTable>
    </el-card>

    <XtFieldGroup v-if="mobileSummary" title="上报闭环" tier="supporting" :items="mobileSummaryFields" />

    <el-card class="panel" v-if="anomalySummary || anomalyItems.length">
      <template #header>异常摘要</template>
      <div class="text-summary">{{ anomalySummary?.digest || '当前未生成异常摘要。' }}</div>
      <ReferenceDataTable v-if="anomalyItems.length" :data="anomalyItems" stripe>
        <el-table-column prop="label" label="异常类型" min-width="140" />
        <el-table-column prop="severity" label="级别" width="100" />
        <el-table-column prop="workshop_id" label="车间" width="100" />
        <el-table-column prop="shift_id" label="班次" width="100" />
        <el-table-column prop="detail" label="说明" min-width="280" />
      </ReferenceDataTable>
    </el-card>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { exportReport, fetchReportDetail } from '../../api/reports'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import { XtFieldGroup } from '../../components/xt'
import {
  formatBooleanLabel,
  formatOutputModeLabel,
  formatReportScopeLabel,
  formatReportTypeLabel,
  formatStatusLabel
} from '../../utils/display'

const route = useRoute()
const report = ref(null)
const reportData = computed(() => report.value?.report_data || {})
const yieldMatrixLane = computed(() => reportData.value.yield_matrix_lane || null)
const preferredYieldRate = computed(() =>
  yieldMatrixLane.value?.quality_status === 'ready'
    ? (yieldMatrixLane.value?.company_total_yield ?? reportData.value.yield_rate ?? '-')
    : (reportData.value.yield_rate ?? '-')
)
const workshopRows = computed(() => reportData.value.workshops || [])
const yieldMatrixWorkshopRows = computed(() =>
  Object.entries(yieldMatrixLane.value?.workshop_yields || {}).map(([workshopKey, yieldRate]) => ({
    workshop_key: workshopKey,
    yield_rate: yieldRate
  }))
)
const mobileSummary = computed(() => reportData.value.mobile_reporting_summary || null)
const anomalySummary = computed(() => reportData.value.anomaly_summary || null)
const anomalyItems = computed(() => reportData.value.anomaly_items || [])
const reportPrimaryFields = computed(() => [
  { label: '报告日期', value: report.value?.report_date },
  { label: '报告类型', value: formatReportTypeLabel(report.value?.report_type) },
  { label: '当前状态', value: formatStatusLabel(report.value?.status) },
  { label: '是否可交付', value: report.value?.delivery_ready ? '是' : '否' },
  { label: '质量闸门', value: formatStatusLabel(report.value?.quality_gate_status), hint: report.value?.quality_gate_summary || '' }
])
const reportSupportingFields = computed(() => [
  { label: '生成范围', value: formatReportScopeLabel(report.value?.generated_scope) },
  { label: '生成时间', value: report.value?.generated_at },
  { label: '发布时间', value: report.value?.published_at },
  { label: '输出方式', value: formatOutputModeLabel(report.value?.output_mode) }
])
const reportAuditFields = computed(() => [
  { label: '报告编号', value: report.value?.id },
  { label: '归档版本', value: formatBooleanLabel(report.value?.is_final_version) },
  { label: '归档确认来源', value: report.value?.final_confirmed_by },
  { label: '归档确认时间', value: report.value?.final_confirmed_at }
])
const metricFields = computed(() => [
  { label: '总产量', value: reportData.value.total_output_weight },
  { label: '总投入', value: reportData.value.total_input_weight },
  { label: '成材率', value: preferredYieldRate.value },
  { label: '出勤', value: reportData.value.total_attendance },
  { label: '总电耗', value: reportData.value.total_electricity_kwh ?? reportData.value.total_energy },
  { label: '单位能耗', value: reportData.value.energy_per_ton },
  { label: '应报班次', value: reportData.value.total_expected },
  { label: '上报率', value: reportData.value.reporting_rate }
])
const mobileSummaryFields = computed(() => [
  { label: '已报', value: mobileSummary.value?.reported_count },
  { label: '未报', value: mobileSummary.value?.unreported_count },
  { label: '退回', value: mobileSummary.value?.returned_count },
  { label: '迟报', value: mobileSummary.value?.late_count }
])
async function load() {
  report.value = await fetchReportDetail(route.params.id)
}

async function download(format) {
  try {
    const { data, headers } = await exportReport(route.params.id, format)
    const contentType = headers['content-type'] || 'application/octet-stream'
    const disposition = headers['content-disposition'] || ''
    const match = disposition.match(/filename=([^;]+)/)
    const filename = match ? match[1].replace(/\"/g, '') : `report_${route.params.id}.${format}`
    const blob = new Blob([data], { type: contentType })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '导出失败')
  }
}

onMounted(load)
</script>

<style scoped>
.report-detail__field-stack {
  display: grid;
  gap: var(--xt-space-3);
}
</style>

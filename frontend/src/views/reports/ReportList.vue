<template>
  <section class="page-stack report-delivery" data-testid="report-delivery-page">
    <header class="report-delivery__hero">
      <div class="report-delivery__hero-copy">
        <span class="report-delivery__eyebrow">日报交付</span>
        <h1>日报与交付中心</h1>
      </div>
      <el-button class="report-delivery__refresh" @click="load">查询</el-button>
    </header>

    <section class="report-delivery__filters" data-testid="report-delivery-filters">
      <el-form inline>
        <el-form-item label="开始日期">
          <el-date-picker v-model="filters.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="filters.end_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="报告类型">
          <el-select v-model="filters.report_type" clearable style="width: 160px">
            <el-option label="生产日报" value="production" />
            <el-option label="考勤日报" value="attendance" />
            <el-option label="异常日报" value="exception" />
          </el-select>
        </el-form-item>
        <el-form-item label="当前状态">
          <el-select v-model="filters.status" clearable style="width: 160px">
            <el-option label="草稿" value="draft" />
            <el-option label="已校验" value="reviewed" />
            <el-option label="已发布" value="published" />
          </el-select>
        </el-form-item>
      </el-form>
    </section>

    <section class="report-delivery__stats" data-testid="report-delivery-stats">
      <article
        v-for="item in reportStats"
        :key="item.key"
        class="report-delivery__stat"
        :class="`report-delivery__stat--${item.accent}`"
      >
        <div class="report-delivery__stat-top">
          <span class="report-delivery__led"></span>
          <span>{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
      </article>
    </section>

    <section class="report-delivery__matrix">
      <div class="report-delivery__matrix-head">
        <div>
          <span class="report-delivery__eyebrow">交付清单</span>
          <h2>交付清单</h2>
        </div>
        <div class="report-delivery__matrix-meta">
          <span>{{ filters.start_date }} - {{ filters.end_date }}</span>
          <span>{{ items.length }} 条</span>
        </div>
      </div>

      <div class="report-delivery__table" data-testid="report-delivery-table">
        <ReferenceDataTable :data="items" stripe>
          <el-table-column prop="id" label="编号" width="78" />
          <el-table-column prop="report_date" label="报告日期" width="112" />
          <el-table-column prop="report_type" label="报告类型" width="118">
            <template #default="{ row }">
              {{ formatReportTypeLabel(row.report_type) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="当前状态" width="112">
            <template #default="{ row }">
              <ReferenceStatusTag :status="statusTone(row.status)" :label="formatReportStatus(row.status)" />
            </template>
          </el-table-column>
          <el-table-column prop="generated_scope" label="生成范围" width="120">
            <template #default="{ row }">
              {{ formatReportScopeLabel(row.generated_scope) }}
            </template>
          </el-table-column>
          <el-table-column prop="output_mode" label="输出方式" width="126">
            <template #default="{ row }">
              {{ formatOutputModeLabel(row.output_mode) }}
            </template>
          </el-table-column>
          <el-table-column prop="is_final_version" label="归档版本" width="112">
            <template #default="{ row }">
              <ReferenceStatusTag :status="row.is_final_version ? 'success' : 'normal'" :label="row.is_final_version ? '最终版' : '过程版'" />
            </template>
          </el-table-column>
          <el-table-column prop="published_at" label="最新输出时间" width="148" />
          <el-table-column label="关键摘要" min-width="190">
            <template #default="{ row }">
              {{ buildSummaryLine(row) }}
            </template>
          </el-table-column>
        </ReferenceDataTable>
      </div>

      <div class="report-delivery__mobile-list" data-testid="report-delivery-mobile-list">
        <article v-for="row in items" :key="row.id || `${row.report_date}-${row.report_type}`">
          <div class="report-delivery__mobile-title">
            <span>{{ row.report_date || '-' }}</span>
            <ReferenceStatusTag :status="statusTone(row.status)" :label="formatReportStatus(row.status)" />
          </div>
          <div class="report-delivery__mobile-grid">
            <span>编号</span><strong>{{ row.id || '-' }}</strong>
            <span>报告类型</span><strong>{{ formatReportTypeLabel(row.report_type) }}</strong>
            <span>生成范围</span><strong>{{ formatReportScopeLabel(row.generated_scope) }}</strong>
            <span>输出方式</span><strong>{{ formatOutputModeLabel(row.output_mode) }}</strong>
            <span>归档版本</span><strong>{{ row.is_final_version ? '最终版' : '过程版' }}</strong>
            <span>最新输出时间</span><strong>{{ row.published_at || '-' }}</strong>
          </div>
          <p>{{ buildSummaryLine(row) }}</p>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { fetchReports } from '../../api/reports'
import { formatOutputModeLabel, formatReportScopeLabel, formatReportTypeLabel, formatStatusLabel } from '../../utils/display'
import { inferBusinessDate } from '../../utils/shiftClock'

const items = ref([])
const defaultBusinessDate = inferBusinessDate()

const filters = reactive({
  start_date: defaultBusinessDate,
  end_date: defaultBusinessDate,
  report_type: '',
  status: ''
})

const reportStats = computed(() => [
  { key: 'total', label: '全部日报', value: formatCount(items.value.length), unit: '份', accent: 'cyan' },
  { key: 'published', label: '已发布', value: formatCount(countByStatus(['published', 'delivered', 'done', 'success'])), unit: '份', accent: 'cyan' },
  { key: 'pending', label: '待处理', value: formatCount(countByStatus(['draft', 'pending', 'generating'])), unit: '份', accent: 'amber' },
  { key: 'final', label: '最终版', value: formatCount(items.value.filter((row) => row?.is_final_version).length), unit: '份', accent: 'blue' }
])

function formatCount(value) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function countByStatus(statuses) {
  const wanted = new Set(statuses)
  return items.value.filter((row) => wanted.has(String(row?.status || '').toLowerCase())).length
}

function buildSummaryLine(row) {
  const reportData = row?.report_data || {}
  const parts = []
  if (reportData.total_output_weight !== undefined) {
    parts.push(`产量 ${reportData.total_output_weight}`)
  }
  if (reportData.reporting_rate !== undefined) {
    parts.push(`上报率 ${reportData.reporting_rate}%`)
  }
  if (reportData.anomaly_summary?.digest) {
    parts.push(`异常 ${reportData.anomaly_summary.digest}`)
  }
  if (reportData.legacy_profile?.items?.length) {
    parts.push(`旁路资料 ${reportData.legacy_profile.items.length} 份`)
  }
  return parts.join('；') || '-'
}

function formatReportStatus(status) {
  if (String(status || '').toLowerCase() === 'reviewed') return '已校验'
  const label = formatStatusLabel(status)
  return label === '已审核' ? '已校验' : label
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['published', 'delivered', 'done', 'success', 'reviewed'].includes(value)) return 'success'
  if (['draft', 'pending', 'generating'].includes(value)) return 'pending'
  if (['failed', 'blocked', 'error'].includes(value)) return 'danger'
  return 'normal'
}

async function load() {
  try {
    const params = { ...filters }
    if (!params.report_type) delete params.report_type
    if (!params.status) delete params.status
    items.value = await fetchReports(params)
  } catch {
    ElMessage.error('日报加载失败')
  }
}

onMounted(load)
</script>

<style scoped>
.report-delivery {
  --report-cyan: #00f2ff;
  --report-cyan-soft: rgba(0, 242, 255, 0.16);
  --report-amber: #ffab00;
  --report-blue: #74f5ff;
  --report-bg: #06101f;
  --report-panel: rgba(12, 25, 42, 0.72);
  --report-line: rgba(0, 242, 255, 0.18);
  --report-muted: rgba(223, 226, 235, 0.66);
  color: #dfe2eb;
}

.report-delivery::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background:
    radial-gradient(circle at 10% 8%, rgba(0, 242, 255, 0.12), transparent 30%),
    radial-gradient(circle at 78% 0%, rgba(116, 245, 255, 0.1), transparent 28%),
    linear-gradient(rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(135deg, #0a0e14, var(--report-bg));
  background-size: auto, auto, 32px 32px, 32px 32px, auto;
}

.report-delivery__hero,
.report-delivery__filters,
.report-delivery__matrix,
.report-delivery__stat,
.report-delivery__mobile-list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--report-line);
  background: linear-gradient(180deg, rgba(38, 42, 49, 0.54), var(--report-panel));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 20px 54px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
}

.report-delivery__hero::after,
.report-delivery__filters::after,
.report-delivery__matrix::after,
.report-delivery__stat::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(115deg, transparent 0%, rgba(0, 242, 255, 0.14) 42%, transparent 62%);
  transform: translateX(-120%);
  animation: reportDeliverySweep 7s ease-in-out infinite;
}

.report-delivery__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 148px;
  padding: 28px;
  border-radius: 18px;
}

.report-delivery__hero-copy,
.report-delivery__refresh,
.report-delivery__filters :deep(.el-form),
.report-delivery__matrix-head,
.report-delivery__table,
.report-delivery__mobile-list {
  position: relative;
  z-index: 1;
}

.report-delivery__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--report-cyan);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.report-delivery__eyebrow::before {
  width: 8px;
  height: 8px;
  content: '';
  border-radius: 999px;
  background: var(--report-cyan);
  box-shadow: 0 0 18px var(--report-cyan);
}

.report-delivery h1,
.report-delivery h2 {
  margin: 0;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  letter-spacing: -0.03em;
}

.report-delivery h1 {
  margin-top: 12px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1;
  text-shadow: 0 0 28px rgba(0, 242, 255, 0.22);
}

.report-delivery h2 {
  margin-top: 8px;
  font-size: 24px;
}

.report-delivery__refresh {
  min-width: 112px;
  border: 1px solid rgba(0, 242, 255, 0.32);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(0, 242, 255, 0.22), rgba(0, 118, 255, 0.32));
  color: #e1fdff;
  font-weight: 800;
  box-shadow: 0 0 26px rgba(0, 242, 255, 0.16);
}

.report-delivery__filters {
  padding: 20px 22px 8px;
  border-radius: 16px;
}

.report-delivery__filters :deep(.el-form) {
  gap: 12px 16px;
  margin: 0;
}

.report-delivery__filters :deep(.el-form-item) {
  margin: 0 0 12px;
}

.report-delivery__filters :deep(.el-form-item__label) {
  color: var(--report-muted);
  font-weight: 700;
}

.report-delivery__filters :deep(.el-input__wrapper),
.report-delivery__filters :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 10px;
  background: rgba(1, 16, 31, 0.72);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.3),
    inset 0 0 0 1px rgba(0, 242, 255, 0.14);
}

.report-delivery__filters :deep(.el-input__inner),
.report-delivery__filters :deep(.el-select__placeholder),
.report-delivery__filters :deep(.el-select__selected-item) {
  color: #e1fdff;
}

.report-delivery__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.report-delivery__stat {
  min-height: 132px;
  padding: 18px;
  border-radius: 16px;
}

.report-delivery__stat-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--report-muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.report-delivery__led {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--report-cyan);
  box-shadow: 0 0 18px var(--report-cyan);
  animation: reportDeliveryPulse 2.2s ease-in-out infinite;
}

.report-delivery__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 18px;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: clamp(30px, 4vw, 46px);
  line-height: 0.95;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.22);
}

.report-delivery__stat small {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  color: var(--report-muted);
  font-weight: 700;
}

.report-delivery__stat--amber .report-delivery__led {
  background: var(--report-amber);
  box-shadow: 0 0 18px var(--report-amber);
}

.report-delivery__stat--blue .report-delivery__led {
  background: var(--report-blue);
  box-shadow: 0 0 18px var(--report-blue);
}

.report-delivery__matrix {
  padding: 22px;
  border-radius: 18px;
}

.report-delivery__matrix-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.report-delivery__matrix-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.report-delivery__matrix-meta span {
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 999px;
  padding: 6px 10px;
  color: var(--report-muted);
  background: rgba(1, 16, 31, 0.62);
  font-size: 12px;
  font-weight: 700;
}

.report-delivery__table {
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 14px;
}

.report-delivery__table :deep(.el-table),
.report-delivery__table :deep(.el-table tr),
.report-delivery__table :deep(.el-table th.el-table__cell),
.report-delivery__table :deep(.el-table td.el-table__cell) {
  background: transparent;
  color: #dfe2eb;
}

.report-delivery__table :deep(.el-table th.el-table__cell) {
  color: rgba(225, 253, 255, 0.82);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.report-delivery__table :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(0, 242, 255, 0.035);
}

.report-delivery__table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(0, 242, 255, 0.08);
}

.report-delivery :deep(.reference-status) {
  border-radius: 999px;
  font-weight: 800;
  letter-spacing: 0.02em;
  box-shadow: 0 0 16px rgba(0, 242, 255, 0.1);
}

.report-delivery__mobile-list {
  display: none;
}

.report-delivery__mobile-list article {
  border-radius: 16px;
  padding: 16px;
}

.report-delivery__mobile-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: 18px;
  font-weight: 800;
}

.report-delivery__mobile-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 14px;
  margin-top: 14px;
}

.report-delivery__mobile-grid span {
  color: var(--report-muted);
}

.report-delivery__mobile-grid strong {
  color: #f6fbff;
  text-align: right;
}

.report-delivery__mobile-list p {
  margin: 14px 0 0;
  color: rgba(223, 226, 235, 0.78);
}

@keyframes reportDeliverySweep {
  0% { transform: translateX(-120%); opacity: 0; }
  42% { opacity: 1; }
  100% { transform: translateX(120%); opacity: 0; }
}

@keyframes reportDeliveryPulse {
  0%, 100% { transform: scale(1); opacity: 0.72; }
  50% { transform: scale(1.22); opacity: 1; }
}

@media (max-width: 1080px) {
  .report-delivery__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .report-delivery__hero,
  .report-delivery__matrix-head {
    align-items: stretch;
    flex-direction: column;
  }

  .report-delivery__refresh {
    width: 100%;
  }

  .report-delivery__filters {
    padding: 16px;
  }

  .report-delivery__filters :deep(.el-form),
  .report-delivery__filters :deep(.el-form-item),
  .report-delivery__filters :deep(.el-date-editor),
  .report-delivery__filters :deep(.el-select) {
    width: 100%;
  }

  .report-delivery__stats {
    grid-template-columns: 1fr;
  }

  .report-delivery__matrix {
    padding: 16px;
  }

  .report-delivery__matrix-meta {
    justify-content: flex-start;
  }

  .report-delivery__table {
    display: none;
  }

  .report-delivery__mobile-list {
    display: grid;
    gap: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .report-delivery__hero::after,
  .report-delivery__filters::after,
  .report-delivery__matrix::after,
  .report-delivery__stat::after,
  .report-delivery__led {
    animation: none;
  }
}
</style>

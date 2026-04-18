<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>日报看板</h1>
        <p>查看日报生成结果、版本状态与交付提示，不在主路径展示审核、发布或确认操作。</p>
      </div>
    </div>

    <el-card class="panel">
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
            <el-option label="已审核" value="reviewed" />
            <el-option label="已发布" value="published" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="panel">
      <el-table :data="items" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="report_date" label="报告日期" width="130" />
        <el-table-column prop="report_type" label="报告类型" width="140">
          <template #default="{ row }">
            {{ formatReportTypeLabel(row.report_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="当前状态" width="120">
          <template #default="{ row }">
            {{ formatStatusLabel(row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="generated_scope" label="统计范围" width="190">
          <template #default="{ row }">
            {{ formatReportScopeLabel(row.generated_scope) }}
          </template>
        </el-table-column>
        <el-table-column prop="output_mode" label="输出方式" width="170">
          <template #default="{ row }">
            {{ formatOutputModeLabel(row.output_mode) }}
          </template>
        </el-table-column>
        <el-table-column prop="is_final_version" label="归档版本" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_final_version ? 'success' : 'info'">
              {{ row.is_final_version ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="published_at" label="最新输出时间" width="200" />
        <el-table-column label="关键摘要" min-width="280">
          <template #default="{ row }">
            {{ buildSummaryLine(row) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchReports } from '../../api/reports'
import { formatOutputModeLabel, formatReportScopeLabel, formatReportTypeLabel, formatStatusLabel } from '../../utils/display'

const router = useRouter()
const items = ref([])

const filters = reactive({
  start_date: dayjs().format('YYYY-MM-DD'),
  end_date: dayjs().format('YYYY-MM-DD'),
  report_type: '',
  status: ''
})

function openDetail(id) {
  router.push({ name: 'report-detail', params: { id } })
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

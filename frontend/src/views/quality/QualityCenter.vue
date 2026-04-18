<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>质量中心</h1>
        <p>查看导入前和发布前的质量问题，并支持处理、忽略与复查。</p>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
        <el-button type="primary" :loading="checking" @click="runChecks">运行质量检查</el-button>
      </div>
    </div>

    <el-card class="panel">
      <el-form inline>
        <el-form-item label="业务日期">
          <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="问题级别">
          <el-select v-model="filters.issue_level" clearable style="width: 160px">
            <el-option label="阻断" value="blocker" />
            <el-option label="预警" value="warning" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题类型">
          <el-select v-model="filters.issue_type" clearable style="width: 220px">
            <el-option label="主数据映射异常" value="master_mapping" />
            <el-option label="关键数据缺失" value="missing_data" />
            <el-option label="数值异常" value="invalid_value" />
            <el-option label="差异未处理" value="unreconciled" />
            <el-option label="发布阻断" value="publish_blocker" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="filters.status" clearable style="width: 160px">
            <el-option label="待处理" value="open" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="ignored" />
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
        <el-table-column prop="business_date" label="业务日期" width="120" />
        <el-table-column prop="issue_level" label="问题级别" width="120">
          <template #default="{ row }">
            {{ formatStatusLabel(row.issue_level) }}
          </template>
        </el-table-column>
        <el-table-column prop="issue_type" label="问题类型" width="160">
          <template #default="{ row }">
            {{ formatQualityIssueTypeLabel(row.issue_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="来源模块" width="140">
          <template #default="{ row }">
            {{ formatSourceTypeLabel(row.source_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="dimension_key" label="维度" width="160" />
        <el-table-column prop="field_name" label="字段" width="140" />
        <el-table-column prop="issue_desc" label="问题描述" min-width="220" />
        <el-table-column prop="status" label="处理状态" width="120">
          <template #default="{ row }">
            {{ formatStatusLabel(row.status) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
            <el-button v-if="row.status === 'open'" link type="success" @click="onResolve(row)">标记已解决</el-button>
            <el-button v-if="row.status === 'open'" link type="warning" @click="onIgnore(row)">忽略问题</el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'

import { fetchQualityIssues, ignoreQualityIssue, resolveQualityIssue, runQualityChecks } from '../../api/quality'
import { formatQualityIssueTypeLabel, formatSourceTypeLabel, formatStatusLabel } from '../../utils/display'

const router = useRouter()
const items = ref([])
const checking = ref(false)
const filters = reactive({
  business_date: dayjs().format('YYYY-MM-DD'),
  issue_type: '',
  issue_level: '',
  status: ''
})

async function load() {
  const params = { ...filters }
  if (!params.issue_type) delete params.issue_type
  if (!params.issue_level) delete params.issue_level
  if (!params.status) delete params.status
  items.value = await fetchQualityIssues(params)
}

async function runChecks() {
  checking.value = true
  try {
    await runQualityChecks({ business_date: filters.business_date })
    ElMessage.success('质量检查完成')
    await load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '质量检查失败')
  } finally {
    checking.value = false
  }
}

function openDetail(id) {
  router.push({ name: 'quality-detail', params: { id } })
}

async function onResolve(row) {
  const { value } = await ElMessageBox.prompt('请输入处理说明', '标记为已解决', {
    confirmButtonText: '提交',
    cancelButtonText: '取消'
  })
  await resolveQualityIssue(row.id, value)
  ElMessage.success('已标记解决')
  await load()
}

async function onIgnore(row) {
  const { value } = await ElMessageBox.prompt('请输入忽略原因', '忽略说明', {
    confirmButtonText: '提交',
    cancelButtonText: '取消'
  })
  await ignoreQualityIssue(row.id, value)
  ElMessage.success('已忽略')
  await load()
}

onMounted(load)
</script>

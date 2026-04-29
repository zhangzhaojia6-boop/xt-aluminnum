<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>班次详情</h1>
        <p>查看生产指标、当前状态、版本信息和处理轨迹。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <div v-if="item" class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">业务日期</div>
        <div class="stat-value">{{ item.business_date }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">班次</div>
        <div class="stat-value">{{ item.shift_code }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">数据状态</div>
        <div class="stat-value"><ReferenceStatusTag :status="statusTone(item.data_status)" :label="formatFlowStatus(item.data_status)" /></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">版本号</div>
        <div class="stat-value">v{{ item.version_no }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">产出量</div>
        <div class="stat-value">{{ item.output_weight ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">合格量</div>
        <div class="stat-value">{{ item.qualified_weight ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">废品量</div>
        <div class="stat-value">{{ item.scrap_weight ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">出勤（实到/计划）</div>
        <div class="stat-value">{{ item.actual_headcount ?? 0 }}/{{ item.planned_headcount ?? 0 }}</div>
      </div>
    </div>

    <el-card class="panel" v-if="item">
      <template #header>状态与版本信息</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="车间">{{ item.workshop_name }}</el-descriptions-item>
        <el-descriptions-item label="班组">{{ item.team_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="设备">{{ item.equipment_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="数据状态">
          <ReferenceStatusTag :status="statusTone(item.data_status)" :label="formatFlowStatus(item.data_status)" />
        </el-descriptions-item>
        <el-descriptions-item label="兼容中间态时间">{{ item.reviewed_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="主链确认时间">{{ item.confirmed_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="驳回原因">{{ item.rejected_reason || '-' }}</el-descriptions-item>
        <el-descriptions-item label="作废原因">{{ item.voided_reason || '-' }}</el-descriptions-item>
        <el-descriptions-item label="替代版本来源">{{ item.superseded_by_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发布时间">{{ item.published_at || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="panel">
      <template #header>关联异常</template>
      <ReferenceDataTable :data="exceptions" stripe>
        <el-table-column label="异常类型" width="180">
          <template #default="{ row }">
            {{ formatExceptionTypeLabel(row.exception_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="exception_desc" label="说明" />
        <el-table-column prop="severity" label="级别" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTone(row.status)" :label="formatStatusLabel(row.status)" />
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>

    <el-card class="panel">
      <template #header>处理轨迹摘要</template>
      <ReferenceDataTable :data="auditTrails" stripe>
        <el-table-column prop="created_at" label="时间" width="200" />
        <el-table-column prop="user_name" label="操作人" width="120" />
        <el-table-column prop="action" label="动作" width="180" />
        <el-table-column prop="reason" label="原因" />
      </ReferenceDataTable>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchShiftProductionDetail } from '../../api/production'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatExceptionTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const item = ref(null)
const exceptions = ref([])
const auditTrails = ref([])

async function load() {
  const data = await fetchShiftProductionDetail(route.params.id)
  item.value = data.item || null
  exceptions.value = data.exceptions || []
  auditTrails.value = data.audit_trails || []
}

function formatFlowStatus(status) {
  const label = formatStatusLabel(status)
  return label === '已审核' ? '已校验' : label
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['closed', 'confirmed', 'success', 'auto_confirmed'].includes(value)) return 'success'
  if (['pending', 'reviewed', 'open', 'warning'].includes(value)) return 'warning'
  if (['abnormal', 'rejected', 'returned', 'failed', 'error'].includes(value)) return 'danger'
  return 'normal'
}

onMounted(load)
</script>

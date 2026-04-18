<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>能耗中心</h1>
        <p>导入能耗数据并查看按业务日期/车间/班次的能耗汇总与单吨能耗。</p>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-card class="panel">
      <el-form inline>
        <el-form-item label="业务日期">
          <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="选择文件">
          <input type="file" accept=".csv,.xlsx" @change="handleFileChange" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="!file" :loading="uploading" @click="submit">导入能耗</el-button>
        </el-form-item>
      </el-form>
      <el-alert
        v-if="summary"
        type="success"
        show-icon
        :title="`批次 ${summary.batch_no} 导入完成`"
        :description="`成功 ${summary.success_rows} 行，失败 ${summary.failed_rows} 行`"
      />
      <pre v-if="summary" class="summary-json">{{ JSON.stringify(summary, null, 2) }}</pre>
    </el-card>

    <el-card class="panel">
      <el-table :data="rows" stripe>
        <el-table-column prop="business_date" label="业务日期" width="120" />
        <el-table-column prop="workshop_code" label="车间" width="120" />
        <el-table-column prop="shift_code" label="班次" width="120" />
        <el-table-column prop="electricity_value" label="电耗" width="120" />
        <el-table-column prop="gas_value" label="气耗" width="120" />
        <el-table-column prop="water_value" label="水耗" width="120" />
        <el-table-column prop="total_energy" label="总能耗" width="120" />
        <el-table-column prop="output_weight" label="产量" width="120" />
        <el-table-column prop="energy_per_ton" label="单吨能耗" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchEnergySummary, importEnergyFile } from '../../api/energy'

const filters = reactive({
  business_date: dayjs().format('YYYY-MM-DD')
})
const rows = ref([])
const summary = ref(null)
const file = ref(null)
const uploading = ref(false)

function handleFileChange(event) {
  const selected = event.target.files?.[0]
  file.value = selected || null
}

async function load() {
  rows.value = await fetchEnergySummary({ business_date: filters.business_date })
}

async function submit() {
  if (!file.value) return
  uploading.value = true
  try {
    const response = await importEnergyFile(file.value)
    summary.value = response.summary
    ElMessage.success('能耗导入完成')
    await load()
  } finally {
    uploading.value = false
  }
}

onMounted(load)
</script>

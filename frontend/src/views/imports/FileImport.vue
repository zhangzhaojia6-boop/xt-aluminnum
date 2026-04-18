<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>文件上传</h1>
        <p>支持排班文件与打卡文件导入，自动生成导入批次和导入行记录。</p>
      </div>
    </div>

    <el-card class="panel">
      <el-form :model="form" label-width="120px">
        <el-form-item label="导入类型">
          <el-select v-model="form.importType" style="width: 280px">
            <el-option label="排班导入 (attendance_schedule)" value="attendance_schedule" />
            <el-option label="打卡导入 (attendance_clock)" value="attendance_clock" />
            <el-option label="生产导入 (production_shift)" value="production_shift" />
            <el-option label="MES导出导入 (mes_export)" value="mes_export" />
            <el-option label="能耗导入 (energy)" value="energy" />
            <el-option label="通用导入 (generic)" value="generic" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板编码">
          <el-input v-model="form.templateCode" style="width: 280px" placeholder="可选，例如 attendance_schedule_default" />
        </el-form-item>
        <el-form-item label="选择文件">
          <input type="file" accept=".csv,.xlsx" @change="handleFileChange" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="!form.file" :loading="uploading" @click="submit">上传并导入</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="summary"
        type="success"
        show-icon
        :title="`批次 ${summary.batch_no} 导入完成`"
        :description="`成功 ${summary.success_rows} 行，失败 ${summary.failed_rows} 行，跳过 ${summary.skipped_rows} 行`"
      />
      <pre v-if="summary" class="summary-json">{{ JSON.stringify(summary, null, 2) }}</pre>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { importClocks, importSchedules } from '../../api/attendance'
import { uploadImport } from '../../api/imports'
import { importProductionFile } from '../../api/production'
import { importMesExport } from '../../api/mes'
import { importEnergyFile } from '../../api/energy'

const uploading = ref(false)
const summary = ref(null)
const form = reactive({
  importType: 'attendance_schedule',
  templateCode: '',
  file: null
})

function handleFileChange(event) {
  const file = event.target.files?.[0]
  form.file = file || null
}

async function submit() {
  if (!form.file) return
  uploading.value = true
  try {
    let response
    if (form.importType === 'attendance_schedule') {
      response = await importSchedules(form.file, form.templateCode || null)
      summary.value = response.summary
    } else if (form.importType === 'attendance_clock') {
      response = await importClocks(form.file, form.templateCode || null)
      summary.value = response.summary
    } else if (form.importType === 'production_shift') {
      response = await importProductionFile(form.file, form.templateCode || null)
      summary.value = response.summary
    } else if (form.importType === 'mes_export') {
      response = await importMesExport(form.file)
      summary.value = response.summary
    } else if (form.importType === 'energy') {
      response = await importEnergyFile(form.file)
      summary.value = response.summary
    } else {
      response = await uploadImport(form.file, 'generic')
      summary.value = response.summary
    }
    ElMessage.success('导入完成')
  } finally {
    uploading.value = false
  }
}
</script>

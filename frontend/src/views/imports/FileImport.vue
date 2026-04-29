<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>文件上传</h1>
        <p>支持排班文件与打卡文件导入，自动生成导入批次和导入行记录。</p>
      </div>
    </div>

    <el-card class="panel">
      <div class="file-import-layout">
        <el-form :model="form" class="file-import-form" label-width="92px">
          <el-form-item label="导入类型">
            <el-select v-model="form.importType" class="file-import-control">
              <el-option label="排班导入 (attendance_schedule)" value="attendance_schedule" />
              <el-option label="打卡导入 (attendance_clock)" value="attendance_clock" />
              <el-option label="生产导入 (production_shift)" value="production_shift" />
              <el-option label="MES导出导入 (mes_export)" value="mes_export" />
              <el-option label="能耗导入 (energy)" value="energy" />
              <el-option label="通用导入 (generic)" value="generic" />
            </el-select>
          </el-form-item>
          <el-form-item label="模板编码">
            <el-input v-model="form.templateCode" class="file-import-control" placeholder="可选，例如 attendance_schedule_default" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :disabled="!form.file" :loading="uploading" @click="submit">上传并导入</el-button>
          </el-form-item>
        </el-form>

        <label class="file-import-drop">
          <input type="file" accept=".csv,.xlsx" @change="handleFileChange" />
          <span>导入文件</span>
          <strong>{{ selectedFileName }}</strong>
          <em>支持 .csv / .xlsx，上传后生成导入批次和行级记录。</em>
        </label>
      </div>

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
import { computed, reactive, ref } from 'vue'
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

const selectedFileName = computed(() => form.file?.name || '点击选择文件')

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

<style scoped>
.file-import-layout {
  display: grid;
  grid-template-columns: minmax(280px, 420px) minmax(320px, 1fr);
  gap: var(--xt-space-5);
  align-items: stretch;
}

.file-import-form {
  min-width: 0;
}

.file-import-control {
  width: min(100%, 320px);
}

.file-import-drop {
  position: relative;
  min-height: 154px;
  display: grid;
  align-content: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-5);
  border: 1px dashed var(--xt-border-strong);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-muted);
  cursor: pointer;
}

.file-import-drop input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.file-import-drop span,
.file-import-drop em {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-style: normal;
}

.file-import-drop strong {
  color: var(--xt-gray-900);
  font-size: var(--xt-text-lg);
}

@media (max-width: 820px) {
  .file-import-layout {
    grid-template-columns: 1fr;
  }
}
</style>

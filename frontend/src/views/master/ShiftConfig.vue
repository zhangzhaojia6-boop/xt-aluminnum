<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>班次配置</h1>
        <p>维护班次基础规则，作为后续班次引擎的输入。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增班次</el-button>
    </div>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column prop="sequence" label="顺序" width="80" />
        <el-table-column prop="start_time" label="开始" width="120" />
        <el-table-column prop="end_time" label="结束" width="120" />
        <el-table-column prop="is_night" label="夜班" width="90">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.is_night ? 'warning' : 'success'" :label="row.is_night ? '是' : '否'" />
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.is_active ? 'success' : 'normal'" :label="row.is_active ? '启用' : '停用'" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑班次' : '新增班次'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="编码">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="顺序">
          <el-input-number v-model="form.sequence" :min="1" :max="99" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-input v-model="form.start_time" placeholder="08:00" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-input v-model="form.end_time" placeholder="16:00" />
        </el-form-item>
        <el-form-item label="夜班">
          <el-switch v-model="form.is_night" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createShiftConfig, deleteShiftConfig, listShiftConfigs, updateShiftConfig } from '../../api/master'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'

const items = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)

const form = reactive({
  code: '',
  name: '',
  sequence: 1,
  start_time: '08:00',
  end_time: '16:00',
  is_night: false,
  is_active: true
})

async function load() {
  items.value = await listShiftConfigs()
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.sequence = 1
  form.start_time = '08:00'
  form.end_time = '16:00'
  form.is_night = false
  form.is_active = true
  editingId.value = null
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.sequence = row.sequence
  form.start_time = row.start_time.slice(0, 5)
  form.end_time = row.end_time.slice(0, 5)
  form.is_night = row.is_night
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editingId.value) {
      await updateShiftConfig(editingId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createShiftConfig({ ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除班次「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteShiftConfig(row.id)
  ElMessage.success('删除成功')
  await load()
}

onMounted(load)
</script>

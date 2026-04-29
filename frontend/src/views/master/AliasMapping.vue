<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>主数据别名映射</h1>
      </div>
      <el-button type="primary" @click="openCreate">新增映射</el-button>
    </div>

    <el-card class="panel">
      <el-form inline>
        <el-form-item label="实体类型">
          <el-select v-model="filters.entity_type" clearable style="width: 160px">
            <el-option label="车间" value="workshop" />
            <el-option label="班组" value="team" />
            <el-option label="班次" value="shift" />
            <el-option label="设备" value="equipment" />
            <el-option label="员工" value="employee" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="filters.source_type" placeholder="例如：mes_export / energy" style="width: 220px" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-select v-model="filters.is_active" clearable style="width: 140px">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="entity_type" label="实体类型" width="140">
          <template #default="{ row }">
            {{ formatEntityTypeLabel(row.entity_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="canonical_code" label="标准编码" width="160" />
        <el-table-column prop="alias_code" label="别名编码" width="160" />
        <el-table-column prop="alias_name" label="别名名称" />
        <el-table-column prop="source_type" label="来源" width="140" />
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑映射' : '新增映射'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="实体类型">
          <el-select v-model="form.entity_type" style="width: 220px">
            <el-option label="车间" value="workshop" />
            <el-option label="班组" value="team" />
            <el-option label="班次" value="shift" />
            <el-option label="设备" value="equipment" />
            <el-option label="员工" value="employee" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准编码">
          <el-input v-model="form.canonical_code" />
        </el-form-item>
        <el-form-item label="别名编码">
          <el-input v-model="form.alias_code" />
        </el-form-item>
        <el-form-item label="别名名称">
          <el-input v-model="form.alias_name" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="form.source_type" placeholder="例如：mes_export / energy" />
        </el-form-item>
        <el-form-item label="是否启用">
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

import { createAliasMapping, deleteAliasMapping, fetchAliasMappings, updateAliasMapping } from '../../api/master'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatEntityTypeLabel } from '../../utils/display'

const items = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)

const filters = reactive({
  entity_type: '',
  source_type: '',
  is_active: ''
})

const form = reactive({
  entity_type: 'workshop',
  canonical_code: '',
  alias_code: '',
  alias_name: '',
  source_type: '',
  is_active: true
})

async function load() {
  const params = { ...filters }
  if (params.entity_type === '') delete params.entity_type
  if (params.source_type === '') delete params.source_type
  if (params.is_active === '') delete params.is_active
  items.value = await fetchAliasMappings(params)
}

function resetForm() {
  form.entity_type = 'workshop'
  form.canonical_code = ''
  form.alias_code = ''
  form.alias_name = ''
  form.source_type = ''
  form.is_active = true
  editingId.value = null
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.entity_type = row.entity_type
  form.canonical_code = row.canonical_code
  form.alias_code = row.alias_code
  form.alias_name = row.alias_name
  form.source_type = row.source_type
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editingId.value) {
      await updateAliasMapping(editingId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createAliasMapping({ ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除映射“${row.alias_code || row.alias_name || row.canonical_code}”吗？`, '提示', {
    type: 'warning'
  })
  await deleteAliasMapping(row.id)
  ElMessage.success('删除成功')
  await load()
}

onMounted(load)
</script>

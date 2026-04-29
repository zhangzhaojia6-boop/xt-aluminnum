<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>班组管理</h1>
        <p>维护班组基础档案，并按车间筛选。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增班组</el-button>
    </div>

    <el-card class="panel">
      <div class="page-filters">
        <span>车间筛选</span>
        <el-select v-model="filterWorkshopId" placeholder="全部车间" clearable style="width: 220px" @change="handleFilterChange">
          <el-option v-for="w in workshops" :key="w.id" :label="w.name" :value="w.id" />
        </el-select>
      </div>

      <ReferenceDataTable :data="items" stripe v-loading="loading">
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="code" label="编码" width="160" />
        <el-table-column prop="name" label="名称" />
        <el-table-column label="所属车间" min-width="160">
          <template #default="{ row }">{{ workshopName(row.workshop_id) }}</template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="90" />
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

      <div class="table-pagination">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :current-page="currentPage"
          :page-size="pageState.limit"
          :total="pageState.total"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑班组' : '新增班组'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="车间">
          <el-select v-model="form.workshop_id" style="width: 100%">
            <el-option v-for="w in workshops" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createTeam, deleteTeam, fetchTeamsPage, fetchWorkshops, updateTeam } from '../../api/master.js'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'

const items = ref([])
const workshops = ref([])
const filterWorkshopId = ref(null)
const dialogVisible = ref(false)
const loading = ref(false)
const saving = ref(false)
const editingId = ref(null)

const pageState = reactive({
  skip: 0,
  limit: 10,
  total: 0
})

const form = reactive({
  workshop_id: null,
  code: '',
  name: '',
  sort_order: 0,
  is_active: true
})

const currentPage = computed(() => Math.floor(pageState.skip / pageState.limit) + 1)

function workshopName(workshopId) {
  return workshops.value.find((item) => item.id === workshopId)?.name || '-'
}

async function load() {
  loading.value = true
  try {
    const page = await fetchTeamsPage({
      workshop_id: filterWorkshopId.value || undefined,
      skip: pageState.skip,
      limit: pageState.limit
    })
    items.value = page.items
    pageState.total = page.total
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  pageState.skip = 0
  load()
}

function handlePageChange(page) {
  pageState.skip = (page - 1) * pageState.limit
  load()
}

function resetForm() {
  form.workshop_id = filterWorkshopId.value || workshops.value[0]?.id || null
  form.code = ''
  form.name = ''
  form.sort_order = 0
  form.is_active = true
  editingId.value = null
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.workshop_id = row.workshop_id
  form.code = row.code
  form.name = row.name
  form.sort_order = row.sort_order || 0
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editingId.value) {
      await updateTeam(editingId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createTeam({ ...form })
      ElMessage.success('新增成功')
      pageState.skip = 0
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除班组「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteTeam(row.id)
  ElMessage.success('删除成功')
  if (pageState.skip >= pageState.total - 1 && pageState.skip > 0) {
    pageState.skip = Math.max(0, pageState.skip - pageState.limit)
  }
  await load()
}

onMounted(async () => {
  workshops.value = await fetchWorkshops({ limit: 500 })
  if (workshops.value.length) {
    form.workshop_id = workshops.value[0].id
  }
  await load()
})
</script>

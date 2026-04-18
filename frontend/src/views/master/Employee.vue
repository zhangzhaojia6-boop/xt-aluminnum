<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>员工管理</h1>
        <p>维护员工基础档案。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增员工</el-button>
    </div>

    <el-card class="panel">
      <div class="page-filters">
        <el-select v-model="filters.workshopId" clearable placeholder="筛选车间" style="width: 220px" @change="handleFilterChange">
          <el-option v-for="workshop in workshops" :key="workshop.id" :label="workshop.name" :value="workshop.id" />
        </el-select>
        <el-select v-model="filters.teamId" clearable placeholder="筛选班组" style="width: 220px" @change="handleFilterChange">
          <el-option v-for="team in availableFilterTeams" :key="team.id" :label="team.name" :value="team.id" />
        </el-select>
      </div>

      <el-table :data="items" stripe v-loading="loading">
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="employee_no" label="工号" width="140" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column label="所属车间" min-width="160">
          <template #default="{ row }">{{ workshopName(row.workshop_id) }}</template>
        </el-table-column>
        <el-table-column label="所属班组" min-width="160">
          <template #default="{ row }">{{ teamName(row.team_id) }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '在职' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑员工' : '新增员工'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="车间">
          <el-select v-model="form.workshop_id" style="width: 100%" @change="handleWorkshopChange">
            <el-option v-for="w in workshops" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="班组">
          <el-select v-model="form.team_id" style="width: 100%" clearable>
            <el-option v-for="t in filteredTeams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工号">
          <el-input v-model="form.employee_no" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
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

import { createEmployee, deleteEmployee, fetchEmployeesPage, fetchTeams, fetchWorkshops, updateEmployee } from '../../api/master.js'

const items = ref([])
const workshops = ref([])
const teams = ref([])
const dialogVisible = ref(false)
const loading = ref(false)
const saving = ref(false)
const editingId = ref(null)

const filters = reactive({
  workshopId: null,
  teamId: null
})

const pageState = reactive({
  skip: 0,
  limit: 10,
  total: 0
})

const form = reactive({
  workshop_id: null,
  team_id: null,
  employee_no: '',
  name: '',
  phone: '',
  is_active: true
})

const currentPage = computed(() => Math.floor(pageState.skip / pageState.limit) + 1)

const filteredTeams = computed(() => {
  if (!form.workshop_id) return teams.value
  return teams.value.filter((team) => team.workshop_id === form.workshop_id)
})

const availableFilterTeams = computed(() => {
  if (!filters.workshopId) return teams.value
  return teams.value.filter((team) => team.workshop_id === filters.workshopId)
})

function workshopName(workshopId) {
  return workshops.value.find((item) => item.id === workshopId)?.name || '-'
}

function teamName(teamId) {
  return teams.value.find((item) => item.id === teamId)?.name || '-'
}

async function load() {
  loading.value = true
  try {
    const page = await fetchEmployeesPage({
      workshop_id: filters.workshopId || undefined,
      team_id: filters.teamId || undefined,
      skip: pageState.skip,
      limit: pageState.limit
    })
    items.value = page.items
    pageState.total = page.total
  } finally {
    loading.value = false
  }
}

function handleWorkshopChange() {
  if (form.team_id && !filteredTeams.value.some((team) => team.id === form.team_id)) {
    form.team_id = null
  }
}

function handleFilterChange() {
  if (filters.teamId && !availableFilterTeams.value.some((team) => team.id === filters.teamId)) {
    filters.teamId = null
  }
  pageState.skip = 0
  load()
}

function handlePageChange(page) {
  pageState.skip = (page - 1) * pageState.limit
  load()
}

function resetForm() {
  form.workshop_id = filters.workshopId || workshops.value[0]?.id || null
  form.team_id = null
  form.employee_no = ''
  form.name = ''
  form.phone = ''
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
  form.team_id = row.team_id
  form.employee_no = row.employee_no
  form.name = row.name
  form.phone = row.phone || ''
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editingId.value) {
      await updateEmployee(editingId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createEmployee({ ...form })
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
  await ElMessageBox.confirm(`确认删除员工「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteEmployee(row.id)
  ElMessage.success('删除成功')
  if (pageState.skip >= pageState.total - 1 && pageState.skip > 0) {
    pageState.skip = Math.max(0, pageState.skip - pageState.limit)
  }
  await load()
}

onMounted(async () => {
  const [workshopItems, teamItems] = await Promise.all([
    fetchWorkshops({ limit: 500 }),
    fetchTeams({ limit: 500 })
  ])
  workshops.value = workshopItems
  teams.value = teamItems
  if (workshops.value.length) {
    form.workshop_id = workshops.value[0].id
  }
  await load()
})
</script>

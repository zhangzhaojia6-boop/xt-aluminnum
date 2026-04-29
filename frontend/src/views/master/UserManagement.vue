<template>
  <ReferencePageFrame
    module-number="13"
    title="权限治理中心"
    :tags="['用户账号', '角色权限', '归属范围']"
    class="page-stack admin-users-center"
    data-testid="admin-users-center"
  >
    <template #actions>
      <el-button type="primary" @click="openCreate">新增用户</el-button>
    </template>

    <el-card class="panel">
      <div class="page-filters">
        <el-select v-model="filters.workshopId" clearable placeholder="筛选车间" style="width: 220px" @change="handleFilterChange">
          <el-option v-for="workshop in workshops" :key="workshop.id" :label="workshop.name" :value="workshop.id" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="账号状态" style="width: 160px" @change="handleFilterChange">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </div>

      <ReferenceDataTable :data="items" stripe v-loading="loading">
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column prop="role" label="角色" min-width="140">
          <template #default="{ row }">
            {{ formatRoleLabel(row.role) }}
          </template>
        </el-table-column>
        <el-table-column prop="workshop_name" label="所属车间" min-width="140">
          <template #default="{ row }">{{ row.workshop_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="team_name" label="所属班组" min-width="140">
          <template #default="{ row }">{{ row.team_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="is_mobile_user" label="手机端" width="90">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.is_mobile_user ? 'success' : 'normal'" :label="row.is_mobile_user ? '是' : '否'" />
          </template>
        </el-table-column>
        <el-table-column prop="is_reviewer" label="观察/处置兼容" width="120">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.is_reviewer ? 'warning' : 'normal'" :label="row.is_reviewer ? '是' : '否'" />
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.is_active ? 'success' : 'normal'" :label="row.is_active ? '启用' : '停用'" />
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最近登录" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.last_login) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text @click="openResetPassword(row)">重置密码</el-button>
            <el-button text type="danger" :disabled="!row.is_active" @click="deactivate(row)">停用</el-button>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户' : '新增用户'" width="640px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="Boolean(editingId)" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="editingId ? '新密码' : '密码'" :required="!editingId">
          <el-input v-model="form.password" type="password" show-password placeholder="编辑时留空表示不修改" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="option in roleOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属车间">
          <el-select v-model="form.workshop_id" clearable style="width: 100%" @change="handleWorkshopChange">
            <el-option v-for="workshop in workshops" :key="workshop.id" :label="workshop.name" :value="workshop.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属班组">
          <el-select v-model="form.team_id" clearable style="width: 100%">
            <el-option v-for="team in filteredTeams" :key="team.id" :label="team.name" :value="team.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="PIN码">
          <el-input v-model="form.pin_code" maxlength="6" placeholder="6位数字，可选" />
        </el-form-item>
        <el-form-item label="账号状态" v-if="editingId">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="权限标记">
          <el-checkbox v-model="form.is_mobile_user">手机端用户</el-checkbox>
          <el-checkbox v-model="form.is_reviewer">观察/处置兼容</el-checkbox>
          <el-checkbox v-model="form.is_manager">管理者</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="480px">
      <el-form :model="resetForm" label-width="100px">
        <el-form-item label="用户名">
          <el-input :model-value="resetTarget?.username || '-'" disabled />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="resetForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="PIN码">
          <el-input v-model="resetForm.pin_code" maxlength="6" placeholder="可选，6位数字" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitResetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { fetchTeams, fetchWorkshops } from '../../api/master.js'
import { createUser, deleteUser, fetchUsersPage, resetUserPassword, updateUser } from '../../api/users.js'
import { formatDateTime, formatRoleLabel } from '../../utils/display.js'

const roleOptions = [
  { value: 'admin', label: '系统管理员' },
  { value: 'factory_director', label: '厂长' },
  { value: 'senior_manager', label: '高级管理' },
  { value: 'manager', label: '车间管理者' },
  { value: 'workshop_director', label: '车间观察者' },
  { value: 'team_leader', label: '班长' },
  { value: 'shift_leader', label: '班长(移动端)' },
  { value: 'weigher', label: '过磅员' },
  { value: 'qc', label: '质检员' },
  { value: 'energy_stat', label: '能耗统计' },
  { value: 'maintenance_lead', label: '机修班长' },
  { value: 'hydraulic_lead', label: '液压班长' },
  { value: 'contracts', label: '合同管理' },
  { value: 'inventory_keeper', label: '成品库负责人' },
  { value: 'utility_manager', label: '水电气负责人' },
  { value: 'statistician', label: '观察角色（旧总统计兼容）' },
  { value: 'reviewer', label: '观察角色（旧审核兼容）' },
  { value: 'mobile_user', label: '移动端填报角色（兼容）' }
]

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const resetDialogVisible = ref(false)
const editingId = ref(null)
const resetTarget = ref(null)
const items = ref([])
const workshops = ref([])
const teams = ref([])

const filters = reactive({
  workshopId: null,
  status: null
})

const pageState = reactive({
  skip: 0,
  limit: 10,
  total: 0
})

const form = reactive({
  username: '',
  password: '',
  name: '',
  role: 'shift_leader',
  workshop_id: null,
  team_id: null,
  pin_code: '',
  is_mobile_user: false,
  is_reviewer: false,
  is_manager: false,
  is_active: true
})

const resetForm = reactive({
  password: '',
  pin_code: ''
})

const filteredTeams = computed(() => {
  if (!form.workshop_id) return teams.value
  return teams.value.filter((team) => team.workshop_id === form.workshop_id)
})

const currentPage = computed(() => Math.floor(pageState.skip / pageState.limit) + 1)

function resetFormState() {
  form.username = ''
  form.password = ''
  form.name = ''
  form.role = 'shift_leader'
  form.workshop_id = null
  form.team_id = null
  form.pin_code = ''
  form.is_mobile_user = false
  form.is_reviewer = false
  form.is_manager = false
  form.is_active = true
  editingId.value = null
}

function handleWorkshopChange() {
  if (form.team_id && !filteredTeams.value.some((team) => team.id === form.team_id)) {
    form.team_id = null
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

function openCreate() {
  resetFormState()
  dialogVisible.value = true
}

function openEdit(row) {
  resetFormState()
  editingId.value = row.id
  form.username = row.username
  form.name = row.name
  form.role = row.role
  form.workshop_id = row.workshop_id
  form.team_id = row.team_id
  form.is_mobile_user = row.is_mobile_user
  form.is_reviewer = row.is_reviewer
  form.is_manager = row.is_manager
  form.is_active = row.is_active
  dialogVisible.value = true
}

function openResetPassword(row) {
  resetTarget.value = row
  resetForm.password = ''
  resetForm.pin_code = ''
  resetDialogVisible.value = true
}

function buildSavePayload() {
  const payload = {
    username: form.username.trim(),
    name: form.name.trim(),
    role: form.role,
    workshop_id: form.workshop_id || null,
    team_id: form.team_id || null,
    is_mobile_user: form.is_mobile_user,
    is_reviewer: form.is_reviewer,
    is_manager: form.is_manager
  }
  if (editingId.value) {
    payload.is_active = form.is_active
    if (form.password.trim()) payload.password = form.password
    if (form.pin_code.trim()) payload.pin_code = form.pin_code.trim()
  } else {
    payload.password = form.password
    if (form.pin_code.trim()) payload.pin_code = form.pin_code.trim()
  }
  return payload
}

async function load() {
  loading.value = true
  try {
    const page = await fetchUsersPage({
      workshop_id: filters.workshopId || undefined,
      is_active: filters.status,
      skip: pageState.skip,
      limit: pageState.limit
    })
    items.value = page.items
    pageState.total = page.total
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.username.trim() || !form.name.trim() || !form.role) {
    ElMessage.warning('请填写完整的用户名、姓名和角色')
    return
  }
  if (!editingId.value && !form.password.trim()) {
    ElMessage.warning('新增用户时必须填写密码')
    return
  }
  saving.value = true
  try {
    const payload = buildSavePayload()
    if (editingId.value) {
      await updateUser(editingId.value, payload)
      ElMessage.success('用户更新成功')
    } else {
      await createUser(payload)
      ElMessage.success('用户创建成功')
      pageState.skip = 0
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function deactivate(row) {
  await ElMessageBox.confirm(`确认停用用户「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('用户已停用')
  await load()
}

async function submitResetPassword() {
  if (!resetTarget.value) return
  if (!resetForm.password.trim()) {
    ElMessage.warning('请输入新密码')
    return
  }
  saving.value = true
  try {
    await resetUserPassword(resetTarget.value.id, {
      password: resetForm.password,
      pin_code: resetForm.pin_code.trim() || undefined
    })
    ElMessage.success('密码已重置')
    resetDialogVisible.value = false
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const [workshopItems, teamItems] = await Promise.all([
      fetchWorkshops({ limit: 500 }),
      fetchTeams({ limit: 500 })
    ])
    workshops.value = workshopItems
    teams.value = teamItems
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
</script>

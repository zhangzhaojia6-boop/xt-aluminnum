<template>
  <section class="page-stack admin-users-center" data-testid="admin-users-center" aria-labelledby="admin-users-title">
    <header class="admin-users-center__hero">
      <div class="admin-users-center__title-group">
        <div class="admin-users-center__title-copy">
          <span class="admin-users-center__system">ACCESS CONTROL MATRIX</span>
          <h1 id="admin-users-title">权限治理中心</h1>
        </div>
        <div class="admin-users-center__tags" aria-label="权限治理范围">
          <span>用户账号</span>
          <span>角色权限</span>
          <span>归属范围</span>
        </div>
      </div>
      <div class="admin-users-center__actions">
        <el-button class="admin-users-center__action" :loading="syncingDingtalk" @click="syncDingtalk">同步钉钉成员</el-button>
        <el-button class="admin-users-center__action admin-users-center__action--primary" type="primary" @click="openCreate">新增用户</el-button>
      </div>
    </header>

    <section class="admin-users-center__status" aria-label="权限账号状态">
      <article
        v-for="stat in governanceStats"
        :key="stat.label"
        class="admin-users-center__stat"
        :class="`is-${stat.tone}`"
      >
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
        <small>{{ stat.meta }}</small>
      </article>
    </section>

    <el-card class="panel admin-users-center__panel" shadow="never">
      <div class="admin-users-center__panel-head">
        <div>
          <span>ACCOUNT MATRIX</span>
          <h2>用户账号</h2>
        </div>
        <strong>{{ pageState.total || items.length }} 条</strong>
      </div>

      <div class="page-filters admin-users-center__filters">
        <el-select v-model="filters.workshopId" clearable placeholder="筛选车间" style="width: 220px" @change="handleWorkshopFilterChange">
          <el-option v-for="workshop in workshops" :key="workshop.id" :label="workshop.name" :value="workshop.id" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="账号状态" style="width: 160px" @change="handleFilterChange">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-select v-model="filters.machineBinding" clearable placeholder="绑定状态" style="width: 160px" @change="handleMachineBindingFilterChange">
          <el-option label="已绑定" value="bound" />
          <el-option label="未绑定" value="unbound" />
        </el-select>
        <el-select
          v-model="filters.boundMachineId"
          clearable
          filterable
          placeholder="筛选机列"
          :disabled="filters.machineBinding === 'unbound'"
          style="width: 220px"
          @change="handleMachineFilterChange"
        >
          <el-option
            v-for="machine in machineFilterOptions"
            :key="machine.id"
            :label="formatMachineLabel(machine)"
            :value="machine.id"
          >
            <div class="machine-option">
              <span class="machine-option__name">{{ formatMachineLabel(machine) }}</span>
              <span v-if="formatMachineBindingOwner(machine)" class="machine-option__owner">已占用 · {{ formatMachineBindingOwner(machine) }}</span>
              <span v-else class="machine-option__owner is-empty">空闲</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <ReferenceDataTable class="admin-users-center__table" :data="items" stripe :fit="false" v-loading="loading">
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
        <el-table-column prop="bound_machine_name" label="绑定机列" min-width="130">
          <template #default="{ row }">{{ row.bound_machine_name || '-' }}</template>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户' : '新增用户'" width="640px" class="admin-users-dialog">
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
          <el-form-item label="所属车间" :required="form.role === 'workshop_director'">
          <el-select v-model="form.workshop_id" clearable style="width: 100%" @change="handleWorkshopChange">
            <el-option v-for="workshop in workshops" :key="workshop.id" :label="workshop.name" :value="workshop.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属班组">
          <el-select v-model="form.team_id" clearable style="width: 100%">
            <el-option v-for="team in filteredTeams" :key="team.id" :label="team.name" :value="team.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定机列">
          <el-select v-model="form.bound_machine_id" clearable filterable style="width: 100%" @change="handleMachineChange">
            <el-option
              v-for="machine in filteredEquipment"
              :key="machine.id"
              :label="formatMachineLabel(machine)"
              :value="machine.id"
              :disabled="Boolean(machine.bound_user_id && machine.bound_user_id !== editingId)"
            >
              <div class="machine-option">
                <span class="machine-option__name">{{ formatMachineLabel(machine) }}</span>
                <span v-if="formatMachineBindingOwner(machine)" class="machine-option__owner">已占用 · {{ formatMachineBindingOwner(machine) }}</span>
                <span v-else class="machine-option__owner is-empty">空闲</span>
              </div>
            </el-option>
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

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="480px" class="admin-users-dialog">
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { fetchEquipment, fetchTeams, fetchWorkshops } from '../../api/master.js'
import { createUser, deleteUser, fetchUsersPage, resetUserPassword, syncDingtalkUsers, updateUser } from '../../api/users.js'
import { formatDateTime, formatRoleLabel } from '../../utils/display.js'

const route = useRoute()

const roleOptions = [
  { value: 'admin', label: '系统管理员' },
  { value: 'factory_director', label: '厂长' },
  { value: 'senior_manager', label: '高级管理' },
  { value: 'manager', label: '车间管理者' },
  { value: 'workshop_director', label: '车间主任' },
  { value: 'energy_stat', label: '电工' },
  { value: 'machine_operator', label: '主操' },
  { value: 'consumable_stat', label: '生产内勤' },
  { value: 'quality_owner', label: '质检内勤 owner' },
  { value: 'planning_owner', label: '计划内勤 owner' },
  { value: 'energy_chief', label: '总电工 owner' },
  { value: 'storage_owner', label: '成品库 owner' },
  { value: 'shipment_outflow_owner', label: '园区剪切 owner' },
  { value: 'recovery_owner', label: '回收 owner' },
  { value: 'overhaul_owner', label: '大修 owner' },
  { value: 'statistician', label: '观察角色（旧总统计兼容）' },
  { value: 'reviewer', label: '观察角色（旧审核兼容）' }
]

const loading = ref(false)
const saving = ref(false)
const syncingDingtalk = ref(false)
const dialogVisible = ref(false)
const resetDialogVisible = ref(false)
const editingId = ref(null)
const resetTarget = ref(null)
const items = ref([])
const workshops = ref([])
const teams = ref([])
const equipment = ref([])

const filters = reactive({
  workshopId: null,
  status: null,
  machineBinding: null,
  boundMachineId: null
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
  role: 'machine_operator',
  workshop_id: null,
  team_id: null,
  bound_machine_id: null,
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

const filteredEquipment = computed(() => {
  if (!form.workshop_id) return equipment.value
  return equipment.value.filter((machine) => machine.workshop_id === form.workshop_id)
})

const machineFilterOptions = computed(() => {
  if (!filters.workshopId) return equipment.value
  return equipment.value.filter((machine) => machine.workshop_id === filters.workshopId)
})

const currentPage = computed(() => Math.floor(pageState.skip / pageState.limit) + 1)
const activeCount = computed(() => items.value.filter((item) => item.is_active).length)
const boundCount = computed(() => items.value.filter((item) => item.bound_machine_id || item.bound_machine_name).length)
const mobileCount = computed(() => items.value.filter((item) => item.is_mobile_user).length)
const boundRate = computed(() => {
  if (!items.value.length) return '0%'
  return `${Math.round((boundCount.value / items.value.length) * 100)}%`
})
const governanceStats = computed(() => [
  { label: '总账号数', value: pageState.total || items.value.length, meta: '当前筛选', tone: 'primary' },
  { label: '启用账号', value: activeCount.value, meta: '本页', tone: 'success' },
  { label: '机列绑定率', value: boundRate.value, meta: '本页', tone: 'warning' },
  { label: '手机端账号', value: mobileCount.value, meta: '本页', tone: 'info' }
])

function routeQueryValue(value) {
  return Array.isArray(value) ? value[0] : value
}

function applyRouteFilters() {
  const machineBinding = routeQueryValue(route.query.machine_binding)
  if (machineBinding === 'bound' || machineBinding === 'unbound') {
    filters.machineBinding = machineBinding
  }

  const boundMachineId = Number(routeQueryValue(route.query.bound_machine_id))
  if (Number.isFinite(boundMachineId) && boundMachineId > 0) {
    filters.boundMachineId = boundMachineId
    filters.machineBinding = 'bound'
  }

  if (filters.machineBinding === 'unbound') {
    filters.boundMachineId = null
  }
}

function resetFormState() {
  form.username = ''
  form.password = ''
  form.name = ''
  form.role = 'machine_operator'
  form.workshop_id = null
  form.team_id = null
  form.bound_machine_id = null
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
  if (form.bound_machine_id && form.workshop_id && !filteredEquipment.value.some((machine) => machine.id === form.bound_machine_id)) {
    form.bound_machine_id = null
  }
}

function handleMachineChange(machineId) {
  const machine = equipment.value.find((item) => item.id === machineId)
  if (!machine) return
  form.workshop_id = machine.workshop_id
  handleWorkshopChange()
}

function formatMachineLabel(machine) {
  return machine.code ? `${machine.name} / ${machine.code}` : machine.name
}

function formatMachineBindingOwner(machine) {
  const name = machine.bound_user_name || machine.boundUserName
  const username = machine.bound_username || machine.boundUsername
  if (name && username) return `${name} / ${username}`
  return name || username || ''
}

function handleFilterChange() {
  pageState.skip = 0
  load()
}

function handleWorkshopFilterChange() {
  if (filters.boundMachineId && !machineFilterOptions.value.some((machine) => machine.id === filters.boundMachineId)) {
    filters.boundMachineId = null
  }
  handleFilterChange()
}

function handleMachineBindingFilterChange() {
  if (filters.machineBinding === 'unbound') {
    filters.boundMachineId = null
  }
  handleFilterChange()
}

function handleMachineFilterChange(machineId) {
  if (machineId) {
    filters.machineBinding = 'bound'
  }
  handleFilterChange()
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
  form.bound_machine_id = row.bound_machine_id
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
  const isWorkshopDirector = form.role === 'workshop_director'
  const payload = {
    username: form.username.trim(),
    name: form.name.trim(),
    role: form.role,
    workshop_id: form.workshop_id || null,
    team_id: form.team_id || null,
    bound_machine_id: form.bound_machine_id ?? null,
    is_mobile_user: form.is_mobile_user,
    is_reviewer: isWorkshopDirector ? true : form.is_reviewer,
    is_manager: isWorkshopDirector ? true : form.is_manager
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
      machine_binding: filters.machineBinding || undefined,
      bound_machine_id: filters.boundMachineId || undefined,
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
  if (form.role === 'workshop_director' && !form.workshop_id) {
    ElMessage.warning('车间主任必须选择所属车间')
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

async function syncDingtalk() {
  await ElMessageBox.confirm('确认从钉钉通讯录同步成员账号吗？', '提示', { type: 'warning' })
  syncingDingtalk.value = true
  try {
    const result = await syncDingtalkUsers({ department_id: 1 })
    const created = Number(result?.created_count || 0)
    const updated = Number(result?.updated_count || 0)
    ElMessage.success(`已同步${created}个，更新${updated}个`)
    pageState.skip = 0
    await load()
  } finally {
    syncingDingtalk.value = false
  }
}

onMounted(async () => {
  try {
    const [workshopItems, teamItems, equipmentItems] = await Promise.all([
      fetchWorkshops({ limit: 500 }),
      fetchTeams({ limit: 500 }),
      fetchEquipment({ limit: 500, reporting_only: true })
    ])
    workshops.value = workshopItems
    teams.value = teamItems
    equipment.value = equipmentItems
    applyRouteFilters()
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
</script>

<style scoped>
.admin-users-center {
  position: relative;
  isolation: isolate;
  display: grid;
  gap: 16px;
  overflow-x: clip;
  background: transparent;
  --users-accent: #00f2ff;
  --users-accent-soft: rgba(0, 242, 255, 0.12);
  --users-bg: rgba(3, 16, 31, 0.92);
  --users-panel: rgba(8, 31, 55, 0.78);
  --users-panel-strong: rgba(11, 42, 70, 0.92);
  --users-line: rgba(0, 242, 255, 0.16);
  --users-line-strong: rgba(0, 242, 255, 0.38);
  --users-text: rgba(225, 253, 255, 0.94);
  --users-muted: rgba(185, 223, 235, 0.64);
  --users-success: #4ecb8a;
  --users-warning: #ffab00;
}

.admin-users-center::before {
  position: absolute;
  inset: -22px 0 auto;
  z-index: -1;
  height: 260px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 14% 18%, rgba(0, 242, 255, 0.2), transparent 26%),
    radial-gradient(circle at 82% 2%, rgba(0, 118, 255, 0.18), transparent 30%),
    linear-gradient(180deg, rgba(6, 30, 55, 0.84), transparent);
  content: "";
  pointer-events: none;
}

.admin-users-center__hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  overflow: hidden;
  padding: 20px;
  border: 1px solid var(--users-line);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(7, 29, 51, 0.92), rgba(2, 13, 26, 0.94)),
    repeating-linear-gradient(90deg, rgba(0, 242, 255, 0.08) 0 1px, transparent 1px 44px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 18px 42px rgba(0, 18, 42, 0.22);
}

.admin-users-center__hero::after {
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.78), transparent);
  animation: usersScanline 4.8s linear infinite;
  content: "";
}

.admin-users-center__title-group {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  min-width: 0;
}

.admin-users-center__title-copy {
  min-width: 0;
}

.admin-users-center__system {
  color: rgba(116, 245, 255, 0.78);
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 0.12em;
}

.admin-users-center__title-copy h1 {
  margin-top: 6px;
  color: var(--users-text);
  font-family: var(--xt-font-number);
  font-size: clamp(26px, 3vw, 40px);
  letter-spacing: -0.03em;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.16);
}

.admin-users-center__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.admin-users-center__tags span {
  border: 1px solid rgba(0, 242, 255, 0.26);
  border-radius: 8px;
  padding: 5px 8px;
  background: rgba(0, 242, 255, 0.08);
  color: rgba(225, 253, 255, 0.82);
  font-size: 12px;
  font-weight: 780;
}

.admin-users-center__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex: 0 0 auto;
}

.admin-users-center__actions :deep(.el-button),
.admin-users-center__action {
  min-height: 38px;
  border-color: rgba(0, 242, 255, 0.28);
  border-radius: 8px;
  background: rgba(1, 16, 31, 0.72);
  color: var(--users-text);
  font-weight: 820;
}

.admin-users-center__actions :deep(.el-button--primary),
.admin-users-center__action--primary {
  border-color: transparent;
  background:
    linear-gradient(180deg, rgba(116, 245, 255, 0.98), rgba(0, 185, 214, 0.92)),
    var(--users-accent);
  color: #00252b;
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.22);
}

.admin-users-center__status {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.admin-users-center__stat {
  position: relative;
  min-height: 108px;
  display: grid;
  align-content: space-between;
  overflow: hidden;
  padding: 16px;
  border: 1px solid var(--users-line);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.82), rgba(3, 14, 27, 0.9)),
    radial-gradient(circle at 100% 0%, rgba(0, 242, 255, 0.12), transparent 34%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.admin-users-center__stat::after {
  position: absolute;
  inset: auto 14px 10px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(0, 242, 255, 0.82), transparent);
  content: "";
}

.admin-users-center__stat span,
.admin-users-center__stat small,
.admin-users-center__panel-head span {
  color: var(--users-muted);
  font-size: 11px;
  font-weight: 840;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.admin-users-center__stat strong {
  color: var(--users-text);
  font-family: var(--xt-font-number);
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1;
}

.admin-users-center__stat.is-success::after {
  background: linear-gradient(90deg, rgba(78, 203, 138, 0.9), transparent);
}

.admin-users-center__stat.is-warning::after {
  background: linear-gradient(90deg, rgba(255, 171, 0, 0.9), transparent);
}

.admin-users-center__panel {
  border: 1px solid var(--users-line);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(7, 29, 51, 0.88), rgba(2, 12, 25, 0.94)),
    var(--users-bg);
  color: var(--users-text);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 22px 52px rgba(0, 18, 42, 0.24);
}

.admin-users-center__panel :deep(.el-card__body) {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.admin-users-center__panel-head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 4px 12px;
  border-bottom: 1px solid rgba(0, 242, 255, 0.12);
}

.admin-users-center__panel-head h2 {
  margin: 4px 0 0;
  color: var(--users-text);
  font-family: var(--xt-font-number);
  font-size: 22px;
  letter-spacing: -0.02em;
}

.admin-users-center__panel-head strong {
  color: #74f5ff;
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 850;
}

.admin-users-center__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 10px;
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.08), transparent 60%),
    rgba(1, 16, 31, 0.66);
}

.admin-users-center__filters :deep(.el-select) {
  min-width: 160px;
}

.admin-users-center__filters :deep(.el-select__wrapper),
.admin-users-center :deep(.el-input__wrapper) {
  min-height: 38px;
  border-radius: 8px;
  background: rgba(1, 16, 31, 0.84);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.24),
    inset 0 0 0 1px rgba(0, 242, 255, 0.16);
}

.admin-users-center__filters :deep(.el-select__placeholder),
.admin-users-center__filters :deep(.el-select__selected-item),
.admin-users-center :deep(.el-input__inner) {
  color: var(--users-text);
}

.admin-users-center :deep(.reference-data-table-shell) {
  width: 100%;
  overflow: hidden;
  border-radius: 10px;
}

.admin-users-center :deep(.admin-users-center__table) {
  --el-table-bg-color: rgba(2, 12, 25, 0.72);
  --el-table-tr-bg-color: rgba(2, 12, 25, 0.72);
  --el-table-row-stripe-bg-color: rgba(0, 242, 255, 0.045);
  --el-table-header-bg-color: rgba(6, 31, 55, 0.94);
  --el-table-row-hover-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-border-color: rgba(0, 242, 255, 0.12);
  --el-table-text-color: rgba(225, 253, 255, 0.9);
  --el-text-color-primary: rgba(225, 253, 255, 0.92);
  --el-text-color-regular: rgba(225, 253, 255, 0.78);
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(2, 12, 25, 0.72);
}

.admin-users-center :deep(.admin-users-center__table .el-table__header-wrapper th) {
  height: 46px;
  color: rgba(116, 245, 255, 0.82);
  font-size: 12px;
  font-weight: 860;
  letter-spacing: 0.06em;
}

.admin-users-center :deep(.admin-users-center__table .el-table__row td) {
  height: 58px;
  border-bottom-color: rgba(0, 242, 255, 0.1);
  background: rgba(2, 12, 25, 0.72);
}

.admin-users-center :deep(.admin-users-center__table .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(0, 242, 255, 0.045);
}

.admin-users-center :deep(.admin-users-center__table .el-table__fixed-right td.el-table__cell),
.admin-users-center :deep(.admin-users-center__table .el-table__fixed-right th.el-table__cell) {
  background: #020c19;
}

.admin-users-center :deep(.admin-users-center__table .el-table__fixed-right),
.admin-users-center :deep(.admin-users-center__table .el-table__fixed-right-patch) {
  background: #020c19;
}

.admin-users-center :deep(.admin-users-center__table .el-table-fixed-column--right.el-table__cell) {
  z-index: 6;
  background: #020c19;
  box-shadow: -14px 0 18px rgba(2, 12, 25, 0.72);
}

.admin-users-center :deep(.admin-users-center__table th.el-table-fixed-column--right.el-table__cell) {
  z-index: 7;
  background: #061f37;
}

.admin-users-center :deep(.admin-users-center__table .el-table-fixed-column--right .cell) {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 10px;
  background: #020c19;
}

.admin-users-center :deep(.admin-users-center__table th.el-table-fixed-column--right .cell) {
  background: #061f37;
}

.admin-users-center :deep(.admin-users-center__table .el-button.is-text) {
  margin-left: 0;
  min-height: 28px;
  padding-inline: 0;
  color: #74f5ff;
  font-weight: 820;
}

.admin-users-center :deep(.admin-users-center__table .el-button.is-text.el-button--danger) {
  color: #ff6b78;
}

.admin-users-center :deep(.table-pagination) {
  display: flex;
  justify-content: flex-end;
  padding-top: 2px;
}

.admin-users-center :deep(.el-pagination.is-background .el-pager li),
.admin-users-center :deep(.el-pagination.is-background button) {
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 7px;
  background: rgba(1, 16, 31, 0.72);
  color: var(--users-muted);
}

.admin-users-center :deep(.el-pagination.is-background .el-pager li.is-active) {
  background: var(--users-accent);
  color: #00252b;
}

.machine-option {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 2px 0;
  line-height: 1.25;
}

.machine-option__name,
.machine-option__owner {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.machine-option__name {
  color: var(--users-text, var(--xt-text));
  font-weight: 820;
}

.machine-option__owner {
  color: oklch(50% 0.13 72);
  font-size: 12px;
  font-weight: 780;
}

.machine-option__owner.is-empty {
  color: var(--users-muted, var(--xt-text-secondary));
}

:global(.admin-users-dialog) {
  --users-accent: #00f2ff;
  --users-line: rgba(0, 242, 255, 0.18);
  --users-text: rgba(225, 253, 255, 0.94);
  border: 1px solid var(--users-line);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(7, 29, 51, 0.98), rgba(2, 12, 25, 0.98));
  color: var(--users-text);
  box-shadow: 0 24px 62px rgba(0, 12, 28, 0.42);
}

:global(.admin-users-dialog .el-dialog__title) {
  color: var(--users-text);
  font-family: var(--xt-font-number);
  font-weight: 850;
}

:global(.admin-users-dialog .el-form-item__label) {
  color: rgba(185, 223, 235, 0.78);
  font-weight: 760;
}

:global(.admin-users-dialog .el-input__wrapper),
:global(.admin-users-dialog .el-select__wrapper) {
  border-radius: 8px;
  background: rgba(1, 16, 31, 0.84);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.24),
    inset 0 0 0 1px rgba(0, 242, 255, 0.16);
}

:global(.admin-users-dialog .el-input__inner),
:global(.admin-users-dialog .el-select__selected-item) {
  color: var(--users-text);
}

@keyframes usersScanline {
  0% { transform: translateX(-45%); opacity: 0.35; }
  50% { opacity: 1; }
  100% { transform: translateX(45%); opacity: 0.35; }
}

@media (max-width: 980px) {
  .admin-users-center__status {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .admin-users-center::before {
    inset-inline: -12px;
  }

  .admin-users-center__hero {
    align-items: stretch;
    flex-direction: column;
    padding: 16px;
  }

  .admin-users-center__title-group {
    align-items: start;
    flex-direction: column;
  }

  .admin-users-center__actions {
    justify-content: stretch;
  }

  .admin-users-center__actions :deep(.el-button),
  .admin-users-center__action {
    flex: 1 1 0;
  }

  .admin-users-center__status {
    grid-template-columns: 1fr;
  }

  .admin-users-center__panel :deep(.el-card__body) {
    padding: 12px;
  }

  .admin-users-center__panel-head {
    align-items: start;
    flex-direction: column;
  }

  .admin-users-center__filters :deep(.el-select) {
    width: 100% !important;
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-users-center__hero::after {
    animation: none;
  }
}
</style>

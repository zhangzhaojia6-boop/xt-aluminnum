<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>机台管理</h1>
        <p>维护机台账号、班制、运行状态、自定义耗材字段和二维码卡片。</p>
      </div>
      <div class="header-actions">
        <el-select v-model="filters.workshopId" clearable placeholder="筛选车间" style="width: 220px" @change="load">
          <el-option v-for="workshop in workshops" :key="workshop.id" :label="workshop.name" :value="workshop.id" />
        </el-select>
        <el-button type="primary" @click="wizardVisible = true">新增机台</el-button>
      </div>
    </div>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe v-loading="loading">
        <el-table-column prop="code" label="编码" min-width="130" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column label="车间" min-width="150">
          <template #default="{ row }">{{ workshopName(row.workshop_id) }}</template>
        </el-table-column>
        <el-table-column label="机器类型" min-width="120">
          <template #default="{ row }">{{ machineTypeLabel(row.equipment_type) }}</template>
        </el-table-column>
        <el-table-column label="班制" min-width="170">
          <template #default="{ row }">
            <ReferenceStatusTag status="normal" :label="row.shift_mode === 'two' ? '两班制' : '三班制'" />
            <span class="machine-table__sub">{{ shiftSummary(row.assigned_shift_ids) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="运行状态" min-width="120">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTagType(row.operational_status)" :label="statusLabel(row.operational_status)" />
          </template>
        </el-table-column>
        <el-table-column label="绑定账号" min-width="170">
          <template #default="{ row }">
            <div>{{ row.bound_username || '-' }}</div>
            <div class="machine-table__sub">{{ row.bound_user_name || '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="二维码" min-width="150">
          <template #default="{ row }">
            <span>{{ row.qr_code || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="320" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text @click="openCustomFields(row)">自定义字段</el-button>
            <el-button text @click="openQr(row)">生成二维码</el-button>
            <el-button text @click="resetPin(row)">重置密码</el-button>
            <el-button
              text
              :type="row.operational_status === 'running' ? 'danger' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.operational_status === 'running' ? '停机' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>

    <MachineWizard
      v-model="wizardVisible"
      :workshops="workshops"
      :shifts="shiftConfigs"
      @created="handleCreated"
    />

    <el-dialog v-model="editVisible" title="编辑机台" width="720px">
      <el-form v-if="editing" label-width="110px">
        <el-form-item label="机台名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="机器类型">
          <el-select v-model="editForm.equipment_type" style="width: 100%">
            <el-option v-for="option in machineTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="班制">
          <el-radio-group v-model="editForm.shift_mode">
            <el-radio-button label="two">两班制</el-radio-button>
            <el-radio-button label="three">三班制</el-radio-button>
          </el-radio-group>
        </el-form-item>
          <el-form-item label="适用班次">
            <el-checkbox-group v-model="editForm.assigned_shift_ids" :disabled="editForm.shift_mode === 'three'">
              <el-checkbox v-for="shift in shiftConfigs" :key="shift.id" :label="shift.id">
                {{ shift.name }}({{ timeRange(shift) }})
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        <el-form-item label="运行状态">
          <el-radio-group v-model="editForm.operational_status">
            <el-radio-button label="running">生产中</el-radio-button>
            <el-radio-button label="stopped">已停机</el-radio-button>
            <el-radio-button label="maintenance">维护中</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="customFieldVisible" title="机台耗材字段" width="900px">
      <div class="machine-wizard__field-list">
        <div
          v-for="(field, index) in customFieldForm"
          :key="`${field.name}-${index}`"
          class="machine-wizard__field-row"
        >
          <el-input v-model="field.name" placeholder="字段名" />
          <el-input v-model="field.label" placeholder="字段标签" />
          <el-select v-model="field.type" placeholder="类型">
            <el-option label="数字" value="number" />
            <el-option label="文本" value="text" />
          </el-select>
          <el-input v-model="field.unit" placeholder="单位" />
          <div class="machine-wizard__field-row-actions">
            <el-button text @click="moveCustomField(index, -1)" :disabled="index === 0">上移</el-button>
            <el-button text @click="moveCustomField(index, 1)" :disabled="index === customFieldForm.length - 1">下移</el-button>
            <el-button text type="danger" @click="removeCustomField(index)">删除</el-button>
          </div>
        </div>
      </div>
      <div class="machine-wizard__footer-actions">
        <el-button type="primary" plain @click="addCustomField">添加字段</el-button>
      </div>
      <template #footer>
        <el-button @click="customFieldVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCustomFields">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="qrVisible" title="机台二维码" width="520px">
      <div v-if="qrTarget" class="machine-qr-card">
        <div class="machine-qr-card__brand">鑫泰铝业 · {{ workshopName(qrTarget.workshop_id) }}</div>
        <div class="machine-qr-card__machine">{{ qrTarget.name }}</div>
        <div v-if="qrImageUrl" class="machine-qr-card__image">
          <img :src="qrImageUrl" alt="机台二维码" />
        </div>
        <div class="machine-qr-card__meta">
          <div>账号：{{ qrTarget.bound_username || '-' }}</div>
          <div>二维码：{{ qrTarget.qr_code || '-' }}</div>
          <div>访问地址：{{ qrLoginUrl }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="qrVisible = false">关闭</el-button>
        <el-button @click="downloadQrImage">下载打印</el-button>
        <el-button type="primary" @click="printQrCard">打印机台卡片</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pinVisible" title="重置密码成功" width="420px">
      <div class="machine-pin-result">
        <div><span>账号：</span><strong>{{ pinResult.username }}</strong></div>
        <div><span>新密码：</span><strong>{{ pinResult.new_pin }}</strong></div>
      </div>
      <template #footer>
        <el-button @click="pinVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import QRCode from 'qrcode'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import MachineWizard from './MachineWizard.vue'
import {
  fetchEquipmentPage,
  fetchShiftConfigs,
  fetchWorkshops,
  resetEquipmentPin,
  toggleEquipmentStatus,
  updateEquipment
} from '../../api/master.js'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'

const machineTypeOptions = [
  { value: 'cast_roller', label: '铸轧机' },
  { value: 'ingot_caster', label: '铸锭线' },
  { value: 'hot_mill', label: '热轧机' },
  { value: 'cold_mill', label: '冷轧机' },
  { value: 'finishing', label: '精整机' },
  { value: 'shear', label: '剪切机' },
  { value: 'straightener', label: '拉弯矫' },
  { value: 'cross_cut', label: '横剪' },
  { value: 'slitter', label: '纵剪/分条' },
  { value: 'recoiler', label: '重卷' },
  { value: 'milling', label: '铣床' },
  { value: 'sawing', label: '锯床' },
  { value: 'other', label: '其他' }
]

const loading = ref(false)
const saving = ref(false)
const wizardVisible = ref(false)
const editVisible = ref(false)
const customFieldVisible = ref(false)
const qrVisible = ref(false)
const pinVisible = ref(false)
const items = ref([])
const workshops = ref([])
const shiftConfigs = ref([])
const editing = ref(null)
const qrTarget = ref(null)
const qrImageUrl = ref('')
const pinResult = reactive({
  username: '',
  new_pin: ''
})

const filters = reactive({
  workshopId: null
})

const editForm = reactive({
  name: '',
  equipment_type: '',
  shift_mode: 'three',
  assigned_shift_ids: [],
  operational_status: 'running'
})

const customFieldForm = ref([])

const qrLoginUrl = computed(() => {
  if (!qrTarget.value?.qr_code) return ''
  return `${window.location.origin}/login?machine=${encodeURIComponent(qrTarget.value.qr_code)}`
})

watch(
  () => editForm.shift_mode,
  (mode) => {
    if (!editVisible.value || !shiftConfigs.value.length) return
    if (mode === 'three') {
      editForm.assigned_shift_ids = shiftConfigs.value.map((item) => item.id)
    } else if (editForm.assigned_shift_ids.length !== 2) {
      editForm.assigned_shift_ids = shiftConfigs.value.slice(0, 2).map((item) => item.id)
    }
  }
)

watch(qrTarget, async (value) => {
  if (!value?.qr_code) {
    qrImageUrl.value = ''
    return
  }
  qrImageUrl.value = await QRCode.toDataURL(qrLoginUrl.value, {
    width: 240,
    margin: 1
  })
})

function timeRange(shift) {
  return `${String(shift.start_time || '').slice(0, 5)}-${String(shift.end_time || '').slice(0, 5)}`
}

function workshopName(workshopId) {
  return workshops.value.find((item) => item.id === workshopId)?.name || '-'
}

function machineTypeLabel(value) {
  return machineTypeOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusLabel(value) {
  if (value === 'running') return '生产中'
  if (value === 'maintenance') return '维护中'
  return '已停机'
}

function statusTagType(value) {
  if (value === 'running') return 'success'
  if (value === 'maintenance') return 'warning'
  return 'danger'
}

function shiftSummary(assignedShiftIds) {
  if (!assignedShiftIds?.length) return '全部班次'
  return shiftConfigs.value
    .filter((shift) => assignedShiftIds.includes(shift.id))
    .map((shift) => shift.name)
    .join(' / ') || '未配置'
}

async function load() {
  loading.value = true
  try {
    const page = await fetchEquipmentPage({
      workshop_id: filters.workshopId || undefined,
      limit: 500
    })
    items.value = page.items
  } finally {
    loading.value = false
  }
}

async function loadMasterData() {
  const [workshopItems, shiftItems] = await Promise.all([
    fetchWorkshops({ limit: 500 }),
    fetchShiftConfigs({ limit: 500 })
  ])
  workshops.value = workshopItems
  shiftConfigs.value = shiftItems
}

function handleCreated() {
  load()
}

function openEdit(row) {
  editing.value = row
  editForm.name = row.name
  editForm.equipment_type = row.equipment_type
  editForm.shift_mode = row.shift_mode || 'three'
  editForm.assigned_shift_ids = Array.isArray(row.assigned_shift_ids) ? [...row.assigned_shift_ids] : shiftConfigs.value.map((item) => item.id)
  editForm.operational_status = row.operational_status || 'running'
  editVisible.value = true
}

function openCustomFields(row) {
  editing.value = row
  customFieldForm.value = Array.isArray(row.custom_fields) ? row.custom_fields.map((field) => ({ ...field })) : []
  customFieldVisible.value = true
}

function addCustomField() {
  customFieldForm.value.push({
    name: '',
    label: '',
    type: 'number',
    unit: ''
  })
}

function removeCustomField(index) {
  customFieldForm.value.splice(index, 1)
}

function moveCustomField(index, delta) {
  const targetIndex = index + delta
  if (targetIndex < 0 || targetIndex >= customFieldForm.value.length) return
  const next = [...customFieldForm.value]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  customFieldForm.value = next
}

async function saveEdit() {
  if (!editing.value) return
  if (editForm.shift_mode === 'two' && editForm.assigned_shift_ids.length !== 2) {
    ElMessage.warning('两班制必须选择 2 个班次。')
    return
  }
  saving.value = true
  try {
    await updateEquipment(editing.value.id, {
      name: editForm.name,
      equipment_type: editForm.equipment_type,
      shift_mode: editForm.shift_mode,
      assigned_shift_ids: [...editForm.assigned_shift_ids],
      operational_status: editForm.operational_status
    })
    ElMessage.success('机台更新成功')
    editVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function saveCustomFields() {
  if (!editing.value) return
  saving.value = true
  try {
    await updateEquipment(editing.value.id, {
      custom_fields: customFieldForm.value.filter((field) => field.name && field.label)
    })
    ElMessage.success('自定义字段已保存')
    customFieldVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function openQr(row) {
  qrTarget.value = row
  qrVisible.value = true
}

async function resetPin(row) {
  await ElMessageBox.confirm(`确认重置机台「${row.name}」的登录密码吗？`, '提示', { type: 'warning' })
  const payload = await resetEquipmentPin(row.id)
  pinResult.username = payload.username
  pinResult.new_pin = payload.new_pin
  pinVisible.value = true
  ElMessage.success('密码已重置')
}

async function toggleStatus(row) {
  const nextStatus = row.operational_status === 'running' ? 'stopped' : 'running'
  if (nextStatus === 'stopped') {
    await ElMessageBox.confirm('确认停机？停机后该机台不再接受填报。', '提示', { type: 'warning' })
  }
  await toggleEquipmentStatus(row.id, nextStatus)
  ElMessage.success(nextStatus === 'running' ? '机台已启用' : '机台已停机')
  await load()
}

function downloadQrImage() {
  if (!qrImageUrl.value || !qrTarget.value) return
  const link = document.createElement('a')
  link.href = qrImageUrl.value
  link.download = `${qrTarget.value.code}-qr.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function printQrCard() {
  if (!qrTarget.value || !qrImageUrl.value) return
  const popup = window.open('', '_blank', 'noopener,noreferrer,width=520,height=720')
  if (!popup) {
    ElMessage.warning('打印窗口被浏览器拦截，请允许弹窗后重试。')
    return
  }
  popup.document.write(`
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>机台卡片</title>
        <style>
          body { margin: 0; font-family: "Microsoft YaHei", sans-serif; background: #f8fafc; }
          .card { width: 320px; margin: 24px auto; padding: 24px; border: 1px solid #dbe3ea; border-radius: 18px; background: #fff; box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12); }
          .brand { font-size: 22px; font-weight: 800; }
          .sub { margin-top: 6px; color: #64748b; }
          .machine { margin-top: 16px; font-size: 28px; font-weight: 800; }
          .qr { margin-top: 20px; text-align: center; }
          .qr img { width: 220px; height: 220px; }
          .meta { margin-top: 18px; display: grid; gap: 8px; font-size: 16px; }
          .foot { margin-top: 18px; color: #64748b; line-height: 1.7; }
        </style>
      </head>
      <body>
        <div class="card">
          <div class="brand">鑫泰铝业</div>
          <div class="sub">${workshopName(qrTarget.value.workshop_id)}</div>
          <div class="machine">${qrTarget.value.name}</div>
          <div class="qr"><img src="${qrImageUrl.value}" alt="机台二维码" /></div>
          <div class="meta">
            <div>账号：${qrTarget.value.bound_username || '-'}</div>
            <div>二维码：${qrTarget.value.qr_code || '-'}</div>
          </div>
          <div class="foot">扫码即可进入机台填报页面</div>
        </div>
        <script>window.onload = () => window.print();<\/script>
      </body>
    </html>
  `)
  popup.document.close()
}

onMounted(async () => {
  try {
    await loadMasterData()
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
</script>

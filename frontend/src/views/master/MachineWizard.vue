<template>
  <el-dialog
    :model-value="modelValue"
    title="新增机台"
    width="920px"
    destroy-on-close
    @close="close"
  >
    <div class="machine-wizard">
      <el-steps :active="activeStep" finish-status="success" simple>
        <el-step title="基本信息" />
        <el-step title="班次配置" />
        <el-step title="耗材字段" />
        <el-step title="账号生成" />
        <el-step title="完成" />
      </el-steps>

      <div v-if="!result" class="machine-wizard__body">
        <section v-show="activeStep === 0" class="machine-wizard__panel">
          <el-form label-width="110px">
            <el-form-item label="所属车间" required>
              <el-select v-model="form.workshop_id" placeholder="请选择车间" style="width: 100%">
                <el-option
                  v-for="workshop in workshops"
                  :key="workshop.id"
                  :label="workshop.name"
                  :value="workshop.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="机台编码" required>
              <el-input v-model="form.code" placeholder="例如：3 或 ZR2-3" />
            </el-form-item>
            <el-form-item label="机台名称" required>
              <el-input v-model="form.name" placeholder="例如：3#机、2050轧机" />
            </el-form-item>
            <el-form-item label="机器类型" required>
              <el-select v-model="form.machine_type" placeholder="请选择机器类型" style="width: 100%">
                <el-option
                  v-for="option in machineTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
          </el-form>

          <div class="machine-wizard__preview">
            <div class="machine-wizard__preview-card">
              <span>预览账号</span>
              <strong>{{ previewUsername || '-' }}</strong>
            </div>
            <div class="machine-wizard__preview-card">
              <span>预览二维码</span>
              <strong>{{ previewQrCode || '-' }}</strong>
            </div>
          </div>
        </section>

        <section v-show="activeStep === 1" class="machine-wizard__panel">
          <el-form label-width="110px">
            <el-form-item label="班制">
              <el-radio-group v-model="form.shift_mode">
                <el-radio-button label="two">两班制</el-radio-button>
                <el-radio-button label="three">三班制</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="适用班次" required>
              <el-checkbox-group v-model="form.assigned_shift_ids" :disabled="form.shift_mode === 'three'">
                <el-checkbox
                  v-for="shift in shiftOptions"
                  :key="shift.id"
                  :label="shift.id"
                >
                  {{ shift.name }}({{ shift.timeRange }})
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="运行状态">
              <el-radio-group v-model="form.operational_status">
                <el-radio-button label="running">立即启用</el-radio-button>
                <el-radio-button label="stopped">暂不启用</el-radio-button>
                <el-radio-button label="maintenance">维护中</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </section>

        <section v-show="activeStep === 2" class="machine-wizard__panel">
          <div class="machine-wizard__preset-row">
            <span>预设模板</span>
            <div class="machine-wizard__preset-actions">
              <el-button @click="applyPreset('cast')">铸轧机耗材</el-button>
              <el-button @click="applyPreset('hotRoll')">热轧耗材</el-button>
              <el-button @click="applyPreset('empty')">空白</el-button>
            </div>
          </div>

          <div class="machine-wizard__field-list">
            <div
              v-for="(field, index) in form.custom_fields"
              :key="`${field.name}-${index}`"
              class="machine-wizard__field-row"
            >
              <el-input v-model="field.name" placeholder="字段名，如 al_liquid_kg" />
              <el-input v-model="field.label" placeholder="字段标签" />
              <el-select v-model="field.type" placeholder="类型">
                <el-option label="数字" value="number" />
                <el-option label="文本" value="text" />
              </el-select>
              <el-input v-model="field.unit" placeholder="单位" />
              <div class="machine-wizard__field-row-actions">
                <el-button text @click="moveField(index, -1)" :disabled="index === 0">上移</el-button>
                <el-button text @click="moveField(index, 1)" :disabled="index === form.custom_fields.length - 1">下移</el-button>
                <el-button text type="danger" @click="removeField(index)">删除</el-button>
              </div>
            </div>
          </div>

          <div class="machine-wizard__footer-actions">
            <el-button type="primary" plain @click="addField">添加字段</el-button>
          </div>

          <div class="machine-wizard__preview machine-wizard__preview--fields">
            <div class="machine-wizard__preview-title">移动端预览</div>
            <div class="machine-wizard__field-preview">
              <div v-if="!form.custom_fields.length" class="machine-wizard__field-preview-empty">当前没有机台耗材字段。</div>
              <div
                v-for="field in form.custom_fields"
                :key="field.name || field.label"
                class="machine-wizard__field-preview-item"
              >
                <span>{{ field.label || '未命名字段' }}</span>
                <strong>{{ field.unit || (field.type === 'number' ? '数字' : '文本') }}</strong>
              </div>
            </div>
          </div>
        </section>

        <section v-show="activeStep === 3" class="machine-wizard__panel">
          <div class="machine-wizard__account-card">
            <div>
              <span>账号</span>
              <strong>{{ previewUsername || '-' }}</strong>
            </div>
            <div>
              <span>预览密码</span>
              <strong>{{ previewPin }}</strong>
            </div>
            <div>
              <span>二维码</span>
              <strong>{{ previewQrCode || '-' }}</strong>
            </div>
          </div>

          <div class="machine-wizard__footer-actions">
            <el-button @click="regeneratePreviewPin">重新生成</el-button>
          </div>
        </section>
      </div>

      <section v-else class="machine-wizard__result">
        <div class="machine-wizard__result-card">
          <div class="machine-wizard__result-title">机台创建成功</div>
          <div class="machine-wizard__result-machine">{{ result.equipment.workshop_name || selectedWorkshop?.name || '' }} · {{ result.equipment.name }}</div>
          <div class="machine-wizard__result-credentials">
            <div><span>账号：</span><strong>{{ result.account.username }}</strong></div>
            <div><span>密码：</span><strong>{{ result.account.pin }}</strong></div>
          </div>
          <div v-if="qrImageUrl" class="machine-wizard__qr-preview">
            <img :src="qrImageUrl" alt="机台二维码" />
          </div>
          <div class="machine-wizard__footer-actions">
            <el-button type="primary" @click="copyCredentials">复制账号密码</el-button>
            <el-button @click="downloadQr">下载二维码</el-button>
            <el-button @click="printCard">打印机台卡片</el-button>
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="machine-wizard__dialog-footer">
        <template v-if="result">
          <el-button @click="close">关闭</el-button>
        </template>
        <template v-else>
          <el-button @click="close">取消</el-button>
          <el-button v-if="activeStep > 0" @click="activeStep -= 1">上一步</el-button>
          <el-button v-if="activeStep < 3" type="primary" @click="goNext">下一步</el-button>
          <el-button v-else type="primary" :loading="saving" @click="submit">创建机台</el-button>
        </template>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import QRCode from 'qrcode'
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { createMachineWithAccount } from '../../api/master.js'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  workshops: {
    type: Array,
    default: () => []
  },
  shifts: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'created'])

const machineTypeOptions = [
  { value: 'cast_roller', label: '铸轧机' },
  { value: 'hot_mill', label: '热轧机' },
  { value: 'cold_mill', label: '冷轧机' },
  { value: 'finishing', label: '精整机' },
  { value: 'shear', label: '剪切机' },
  { value: 'milling', label: '铣床' },
  { value: 'sawing', label: '锯床' },
  { value: 'other', label: '其他' }
]

const castPreset = [
  { name: 'al_liquid_kg', label: '铝液', type: 'number', unit: '公斤' },
  { name: 'cast_cut_count', label: '铸轧削', type: 'number', unit: '个' },
  { name: 'al_rod', label: '铝棒', type: 'number', unit: '个' },
  { name: 'fine_roll', label: '精轧', type: 'number', unit: '个' },
  { name: 'coarse_roll', label: '粗轧', type: 'number', unit: '个' },
  { name: 'back_plate', label: '背板', type: 'number', unit: '个' },
  { name: 'tip_plate', label: '嘴片', type: 'number', unit: '个' },
  { name: 'graphite_ring', label: '石墨环', type: 'number', unit: '个' },
  { name: 'filter_plate', label: '过滤板', type: 'number', unit: '个' },
  { name: 'silica_tube', label: '硅碳管', type: 'number', unit: '根' },
  { name: 'mn_agent_kg', label: '锰剂', type: 'number', unit: '公斤' }
]

const hotRollPreset = [
  { name: 'trim_weight', label: '切头重量', type: 'number', unit: 'kg' },
  { name: 'oil_consumption', label: '润滑油', type: 'number', unit: 'L' }
]

const activeStep = ref(0)
const saving = ref(false)
const result = ref(null)
const qrImageUrl = ref('')
const previewPin = ref(generatePreviewPin())

const form = reactive({
  workshop_id: null,
  code: '',
  name: '',
  machine_type: '',
  shift_mode: 'three',
  assigned_shift_ids: [],
  custom_fields: [],
  operational_status: 'running'
})

const shiftOptions = computed(() => {
  if (props.shifts.length) {
    return props.shifts.map((shift) => ({
      id: shift.id,
      code: shift.code,
      name: shift.name,
      timeRange: `${String(shift.start_time || '').slice(0, 5)}-${String(shift.end_time || '').slice(0, 5)}`
    }))
  }
  return [
    { id: 1, code: 'A', name: '白班', timeRange: '07:00-15:00' },
    { id: 2, code: 'B', name: '小夜', timeRange: '15:00-23:00' },
    { id: 3, code: 'C', name: '大夜', timeRange: '23:00-07:00' }
  ]
})

const selectedWorkshop = computed(() => props.workshops.find((item) => item.id === form.workshop_id) || null)
const previewUsername = computed(() => {
  const workshopCode = selectedWorkshop.value?.code || ''
  const machineCode = normalizeMachineCode(workshopCode, form.code)
  return machineCode || ''
})
const previewQrCode = computed(() => (previewUsername.value ? `XT-${previewUsername.value}` : ''))
const qrLoginUrl = computed(() => (result.value ? `${window.location.origin}/mobile?machine=${encodeURIComponent(result.value.account.qr_code)}` : ''))

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      resetWizard()
    }
  }
)

watch(
  () => form.shift_mode,
  (mode) => {
    if (mode === 'three') {
      form.assigned_shift_ids = shiftOptions.value.map((item) => item.id)
      return
    }
    form.assigned_shift_ids = shiftOptions.value.slice(0, 2).map((item) => item.id)
  },
  { immediate: true }
)

watch(result, async (value) => {
  if (!value) {
    qrImageUrl.value = ''
    return
  }
  qrImageUrl.value = await QRCode.toDataURL(qrLoginUrl.value, {
    width: 240,
    margin: 1
  })
})

function close() {
  emit('update:modelValue', false)
}

function resetWizard() {
  activeStep.value = 0
  saving.value = false
  result.value = null
  qrImageUrl.value = ''
  previewPin.value = generatePreviewPin()
  form.workshop_id = props.workshops[0]?.id ?? null
  form.code = ''
  form.name = ''
  form.machine_type = ''
  form.shift_mode = 'three'
  form.assigned_shift_ids = shiftOptions.value.map((item) => item.id)
  form.custom_fields = []
  form.operational_status = 'running'
}

function normalizeMachineCode(workshopCode, value) {
  const normalizedWorkshop = String(workshopCode || '').trim().toUpperCase().replace(/[^0-9A-Z_-]+/g, '')
  const normalizedCode = String(value || '').trim().toUpperCase().replace(/[^0-9A-Z_-]+/g, '')
  if (!normalizedWorkshop || !normalizedCode) return ''
  if (normalizedCode.startsWith(`${normalizedWorkshop}-`)) return normalizedCode
  return `${normalizedWorkshop}-${normalizedCode}`
}

function generatePreviewPin() {
  return String(Math.floor(Math.random() * 1000000)).padStart(6, '0')
}

function regeneratePreviewPin() {
  previewPin.value = generatePreviewPin()
}

function addField() {
  form.custom_fields.push({
    name: '',
    label: '',
    type: 'number',
    unit: ''
  })
}

function removeField(index) {
  form.custom_fields.splice(index, 1)
}

function moveField(index, delta) {
  const targetIndex = index + delta
  if (targetIndex < 0 || targetIndex >= form.custom_fields.length) return
  const next = [...form.custom_fields]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  form.custom_fields = next
}

function applyPreset(type) {
  if (type === 'cast') {
    form.custom_fields = castPreset.map((item) => ({ ...item }))
    return
  }
  if (type === 'hotRoll') {
    form.custom_fields = hotRollPreset.map((item) => ({ ...item }))
    return
  }
  form.custom_fields = []
}

function validateStep(index) {
  if (index === 0) {
    if (!form.workshop_id || !form.code.trim() || !form.name.trim() || !form.machine_type) {
      ElMessage.warning('请先填写完整的机台基本信息。')
      return false
    }
  }

  if (index === 1) {
    if (form.shift_mode === 'two' && form.assigned_shift_ids.length !== 2) {
      ElMessage.warning('两班制必须选择且仅选择 2 个班次。')
      return false
    }
    if (form.shift_mode === 'three' && form.assigned_shift_ids.length !== 3) {
      ElMessage.warning('三班制必须包含全部 3 个班次。')
      return false
    }
  }

  if (index === 2) {
    const invalidField = form.custom_fields.find((field) => field.label && !field.name)
    if (invalidField) {
      ElMessage.warning('自定义字段填写了标签时，字段名也必须填写。')
      return false
    }
  }

  return true
}

function goNext() {
  if (!validateStep(activeStep.value)) return
  activeStep.value += 1
}

async function submit() {
  if (!validateStep(0) || !validateStep(1) || !validateStep(2)) return
  saving.value = true
  try {
    const payload = await createMachineWithAccount({
      workshop_id: form.workshop_id,
      code: form.code,
      name: form.name,
      machine_type: form.machine_type,
      shift_mode: form.shift_mode,
      assigned_shift_ids: [...form.assigned_shift_ids],
      custom_fields: form.custom_fields
        .filter((field) => field.name && field.label)
        .map((field) => ({
          name: field.name,
          label: field.label,
          type: field.type || 'number',
          unit: field.unit || ''
        })),
      operational_status: form.operational_status
    })
    result.value = payload
    activeStep.value = 4
    emit('created', payload)
    ElMessage.success(payload.message || '机台创建成功')
  } finally {
    saving.value = false
  }
}

async function copyCredentials() {
  if (!result.value) return
  await navigator.clipboard.writeText(`账号：${result.value.account.username}\n密码：${result.value.account.pin}\n二维码：${result.value.account.qr_code}`)
  ElMessage.success('账号密码已复制')
}

function downloadQr() {
  if (!qrImageUrl.value || !result.value) return
  const link = document.createElement('a')
  link.href = qrImageUrl.value
  link.download = `${result.value.account.username}-qr.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function printCard() {
  if (!result.value || !qrImageUrl.value) return
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
          <div class="sub">${selectedWorkshop.value?.name || ''}</div>
          <div class="machine">${result.value.equipment.name}</div>
          <div class="qr"><img src="${qrImageUrl.value}" alt="机台二维码" /></div>
          <div class="meta">
            <div>账号：${result.value.account.username}</div>
            <div>密码：${result.value.account.pin}</div>
            <div>二维码：${result.value.account.qr_code}</div>
          </div>
          <div class="foot">扫码或输入账号登录填报页面</div>
        </div>
        <script>window.onload = () => window.print();<\/script>
      </body>
    </html>
  `)
  popup.document.close()
}
</script>

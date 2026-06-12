<template>
  <div class="terminal-binding page-stack" data-testid="mes-terminal-binding-page">
    <section class="terminal-binding__hero">
      <div>
        <span>MES 终端绑定</span>
        <h1>MES 终端绑定</h1>
      </div>
      <div class="terminal-binding__stats">
        <article>
          <span>绑定规则</span>
          <strong>{{ items.length }}</strong>
        </article>
        <article>
          <span>启用</span>
          <strong>{{ enabledCount }}</strong>
        </article>
        <article class="is-amber">
          <span>PC 终端</span>
          <strong>{{ pcCount }}</strong>
        </article>
      </div>
      <el-button type="primary" class="terminal-binding__primary" @click="openCreate">
        新增绑定
      </el-button>
    </section>

    <section class="terminal-binding__filters">
      <el-form inline>
        <el-form-item label="终端编码">
          <el-input v-model="filters.terminal_code" placeholder="PC-JZ-01" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="车间">
          <el-input v-model="filters.workshop_name" placeholder="精整 / 在线退火" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="工艺">
          <el-input v-model="filters.process_name" placeholder="包装 / 冷轧" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.is_active" clearable style="width: 120px">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="terminal-binding__table-card">
      <header>
        <div>
          <span>绑定清单</span>
          <strong>终端到机列</strong>
        </div>
        <small>PC 只有命中规则才归机列</small>
      </header>

      <ReferenceDataTable
        :data="items"
        stripe
        v-loading="loading"
        class="terminal-binding__table"
        data-testid="mes-terminal-binding-table"
      >
        <el-table-column prop="terminal_code" label="终端编码" min-width="150" />
        <el-table-column prop="terminal_name" label="终端名称" min-width="150">
          <template #default="{ row }">{{ row.terminal_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="mes_device_name" label="MES设备名" width="120">
          <template #default="{ row }">{{ row.mes_device_name || 'PC' }}</template>
        </el-table-column>
        <el-table-column prop="workshop_name" label="车间" width="140">
          <template #default="{ row }">{{ row.workshop_name || '不限' }}</template>
        </el-table-column>
        <el-table-column prop="process_name" label="工艺" width="120">
          <template #default="{ row }">{{ row.process_name || '不限' }}</template>
        </el-table-column>
        <el-table-column label="机列" min-width="170">
          <template #default="{ row }">
            <span>{{ equipmentLabel(row.equipment_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="可信度" width="100" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <span class="terminal-binding__status" :class="{ 'is-off': !row.is_active }">
              <i aria-hidden="true"></i>
              {{ row.is_active ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" :disabled="!row.is_active" @click="remove(row)">停用</el-button>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑终端绑定' : '新增终端绑定'" width="620px" class="terminal-binding__dialog">
      <el-form :model="form" label-width="110px">
        <el-form-item label="终端编码">
          <el-input v-model="form.terminal_code" placeholder="PC-JZ-01" />
        </el-form-item>
        <el-form-item label="终端名称">
          <el-input v-model="form.terminal_name" placeholder="精整包装一体机" />
        </el-form-item>
        <el-form-item label="MES设备名">
          <el-input v-model="form.mes_device_name" placeholder="PC" />
        </el-form-item>
        <el-form-item label="车间">
          <el-input v-model="form.workshop_name" placeholder="精整" />
        </el-form-item>
        <el-form-item label="工艺">
          <el-input v-model="form.process_name" placeholder="包装" />
        </el-form-item>
        <el-form-item label="机列">
          <el-select v-model="form.equipment_id" filterable style="width: 100%">
            <el-option
              v-for="item in equipmentItems"
              :key="item.id"
              :label="`${item.name}（${item.code}）`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="可信度">
          <el-select v-model="form.confidence" style="width: 180px">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
          </el-select>
        </el-form-item>
        <el-form-item label="生效时间">
          <el-date-picker v-model="form.valid_from" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="失效时间">
          <el-date-picker v-model="form.valid_to" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createMesTerminalBinding,
  deleteMesTerminalBinding,
  fetchEquipment,
  fetchMesTerminalBindings,
  updateMesTerminalBinding
} from '../../api/master'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'

const items = ref([])
const equipmentItems = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)

const filters = reactive({
  terminal_code: '',
  workshop_name: '',
  process_name: '',
  is_active: ''
})

const form = reactive({
  terminal_code: '',
  terminal_name: '',
  mes_device_name: 'PC',
  workshop_name: '',
  process_name: '',
  equipment_id: null,
  confidence: 'high',
  valid_from: null,
  valid_to: null,
  is_active: true
})

const enabledCount = computed(() => items.value.filter((item) => item.is_active !== false).length)
const pcCount = computed(() => items.value.filter((item) => String(item.mes_device_name || 'PC').toUpperCase() === 'PC').length)

function normalizeParams() {
  const params = { ...filters }
  for (const key of ['terminal_code', 'workshop_name', 'process_name']) {
    if (!params[key]) delete params[key]
  }
  if (params.is_active === '') delete params.is_active
  return params
}

function resetForm() {
  editingId.value = null
  form.terminal_code = ''
  form.terminal_name = ''
  form.mes_device_name = 'PC'
  form.workshop_name = ''
  form.process_name = ''
  form.equipment_id = null
  form.confidence = 'high'
  form.valid_from = null
  form.valid_to = null
  form.is_active = true
}

function equipmentLabel(id) {
  const item = equipmentItems.value.find((equipment) => Number(equipment.id) === Number(id))
  return item ? `${item.name}（${item.code}）` : `#${id}`
}

async function load() {
  loading.value = true
  try {
    const [bindings, equipment] = await Promise.all([
      fetchMesTerminalBindings(normalizeParams()),
      fetchEquipment({ limit: 500 })
    ])
    items.value = bindings
    equipmentItems.value = equipment
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.terminal_code = row.terminal_code || ''
  form.terminal_name = row.terminal_name || ''
  form.mes_device_name = row.mes_device_name || 'PC'
  form.workshop_name = row.workshop_name || ''
  form.process_name = row.process_name || ''
  form.equipment_id = row.equipment_id
  form.confidence = row.confidence || 'high'
  form.valid_from = row.valid_from || null
  form.valid_to = row.valid_to || null
  form.is_active = row.is_active !== false
  dialogVisible.value = true
}

function buildPayload() {
  return {
    ...form,
    terminal_name: form.terminal_name || null,
    mes_device_name: form.mes_device_name || 'PC',
    workshop_name: form.workshop_name || null,
    process_name: form.process_name || null,
    valid_from: form.valid_from || null,
    valid_to: form.valid_to || null
  }
}

async function save() {
  saving.value = true
  try {
    if (editingId.value) {
      await updateMesTerminalBinding(editingId.value, buildPayload())
      ElMessage.success('更新成功')
    } else {
      await createMesTerminalBinding(buildPayload())
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认停用终端“${row.terminal_code}”吗？`, '提示', { type: 'warning' })
  await deleteMesTerminalBinding(row.id)
  ElMessage.success('停用成功')
  await load()
}

onMounted(load)
</script>

<style scoped>
.terminal-binding {
  --terminal-cyan: #00f2ff;
  --terminal-amber: #ffab00;
  --terminal-bg: rgba(2, 15, 29, 0.72);
  --terminal-line: rgba(0, 242, 255, 0.18);
  --terminal-text: rgba(225, 253, 255, 0.94);
  color: var(--terminal-text);
}

.terminal-binding__hero,
.terminal-binding__filters,
.terminal-binding__table-card {
  border: 1px solid var(--terminal-line);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(18, 44, 70, 0.54), rgba(4, 14, 26, 0.78)),
    var(--terminal-bg);
  box-shadow: inset 1px 1px 0 rgba(255, 255, 255, 0.05);
}

.terminal-binding__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4);
}

.terminal-binding__hero span,
.terminal-binding__table-card header span {
  color: rgba(116, 245, 255, 0.86);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.12em;
}

.terminal-binding__hero h1 {
  margin: var(--xt-space-1) 0 0;
  font-family: var(--xt-font-display);
  font-size: clamp(30px, 4vw, 50px);
  line-height: 1;
}

.terminal-binding__stats {
  display: flex;
  gap: var(--xt-space-3);
}

.terminal-binding__stats article {
  min-width: 104px;
  padding: var(--xt-space-3);
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 12px;
  background: rgba(3, 18, 34, 0.5);
}

.terminal-binding__stats strong {
  display: block;
  margin-top: var(--xt-space-1);
  color: var(--terminal-cyan);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-2xl);
}

.terminal-binding__stats .is-amber strong {
  color: var(--terminal-amber);
}

.terminal-binding__primary {
  min-width: 120px;
}

.terminal-binding__filters,
.terminal-binding__table-card {
  padding: var(--xt-space-4);
}

.terminal-binding__filters :deep(.el-form-item__label),
.terminal-binding__dialog :deep(.el-form-item__label) {
  color: rgba(225, 253, 255, 0.86);
  font-weight: 850;
}

.terminal-binding__table-card {
  display: grid;
  gap: var(--xt-space-3);
}

.terminal-binding__table-card header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-3);
}

.terminal-binding__table-card header strong {
  display: block;
  margin-top: 4px;
  font-size: var(--xt-text-xl);
}

.terminal-binding__table-card header small {
  color: rgba(185, 202, 203, 0.72);
  font-weight: 800;
}

.terminal-binding__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(137, 255, 205, 0.94);
  font-weight: 850;
}

.terminal-binding__status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(66, 211, 146, 0.95);
  box-shadow: 0 0 10px rgba(66, 211, 146, 0.7);
}

.terminal-binding__status.is-off {
  color: rgba(185, 202, 203, 0.68);
}

.terminal-binding__status.is-off i {
  background: rgba(132, 148, 149, 0.7);
  box-shadow: none;
}

.terminal-binding :deep(.reference-data-table-shell) {
  border-color: rgba(0, 242, 255, 0.14);
  background: rgba(3, 18, 34, 0.35);
}

:deep(.terminal-binding__dialog .el-dialog) {
  border: 1px solid rgba(0, 242, 255, 0.2);
  background: rgba(3, 18, 34, 0.96);
}

:deep(.terminal-binding__dialog .el-dialog__title) {
  color: rgba(225, 253, 255, 0.94);
}

@media (max-width: 900px) {
  .terminal-binding__hero {
    grid-template-columns: 1fr;
  }

  .terminal-binding__stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .terminal-binding__stats {
    grid-template-columns: 1fr;
  }
}
</style>

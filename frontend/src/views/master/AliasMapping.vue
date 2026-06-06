<template>
  <div class="page-stack alias-router" data-testid="alias-router-page">
    <section class="alias-router__hero" aria-labelledby="alias-router-title">
      <div class="alias-router__title-block">
        <span class="alias-router__eyebrow">ALIAS ROUTER</span>
        <h1 id="alias-router-title">主数据别名映射</h1>
      </div>

      <div class="alias-router__stats" aria-label="别名映射统计">
        <article
          v-for="stat in aliasStats"
          :key="stat.key"
          class="alias-router__stat"
          :class="`is-${stat.tone}`"
        >
          <span>{{ stat.label }}</span>
          <strong>{{ stat.value }}</strong>
        </article>
      </div>

      <el-button class="alias-router__primary-action" type="primary" @click="openCreate">
        新增映射
      </el-button>
    </section>

    <section class="alias-router__scanbar" data-testid="alias-filter-panel">
      <el-form class="alias-router__filters" inline>
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
          <el-input v-model="filters.source_type" placeholder="mes_export / energy" style="width: 220px" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-select v-model="filters.is_active" clearable style="width: 140px">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button class="alias-router__query" type="primary" :loading="loading" @click="load">
            查询
          </el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="alias-router__matrix" data-testid="alias-matrix">
      <header class="alias-router__matrix-head">
        <div>
          <span>DATA MATRIX</span>
          <strong>映射链路</strong>
        </div>
        <small>{{ items.length }} 条记录</small>
      </header>

      <div class="alias-router__matrix-scroll">
        <ReferenceDataTable :data="items" stripe v-loading="loading" class="alias-router__table" data-testid="alias-table">
          <el-table-column prop="id" label="编号" width="90" />
          <el-table-column prop="entity_type" label="实体类型" width="140">
            <template #default="{ row }">
              <span class="alias-router__type-chip">{{ formatEntityTypeLabel(row.entity_type) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="canonical_code" label="标准编码" width="160" />
          <el-table-column prop="alias_code" label="别名编码" width="160" />
          <el-table-column prop="alias_name" label="别名名称" min-width="180" />
          <el-table-column prop="source_type" label="来源" width="150">
            <template #default="{ row }">
              <span class="alias-router__source">{{ row.source_type || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="110">
            <template #default="{ row }">
              <span class="alias-router__status" :class="{ 'is-off': !row.is_active }">
                <i aria-hidden="true"></i>
                {{ row.is_active ? '启用' : '停用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button text type="danger" :disabled="!row.is_active" @click="remove(row)">停用</el-button>
            </template>
          </el-table-column>
        </ReferenceDataTable>
      </div>

      <div class="alias-router__mobile-list" data-testid="alias-mobile-list">
        <article v-for="row in items" :key="row.id" class="alias-router__mobile-card">
          <header>
            <span>{{ row.id }}</span>
            <span class="alias-router__status" :class="{ 'is-off': !row.is_active }">
              <i aria-hidden="true"></i>
              {{ row.is_active ? '启用' : '停用' }}
            </span>
          </header>
          <div class="alias-router__mobile-type">
            <span class="alias-router__type-chip">{{ formatEntityTypeLabel(row.entity_type) }}</span>
            <strong>{{ row.alias_name || row.alias_code || row.canonical_code }}</strong>
          </div>
          <dl>
            <div>
              <dt>标准编码</dt>
              <dd>{{ row.canonical_code || '-' }}</dd>
            </div>
            <div>
              <dt>别名编码</dt>
              <dd>{{ row.alias_code || '-' }}</dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd>{{ row.source_type || '-' }}</dd>
            </div>
          </dl>
          <footer>
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" :disabled="!row.is_active" @click="remove(row)">停用</el-button>
          </footer>
        </article>
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑映射' : '新增映射'" width="560px" class="alias-router__dialog">
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
          <el-input v-model="form.source_type" placeholder="mes_export / energy" />
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

import { createAliasMapping, deleteAliasMapping, fetchAliasMappings, updateAliasMapping } from '../../api/master'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import { formatEntityTypeLabel } from '../../utils/display'

const items = ref([])
const loading = ref(false)
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

const enabledCount = computed(() => items.value.filter((item) => item.is_active !== false).length)
const disabledCount = computed(() => items.value.filter((item) => item.is_active === false).length)
const aliasStats = computed(() => [
  { key: 'total', label: '映射总数', value: items.value.length, tone: 'primary' },
  { key: 'enabled', label: '启用映射', value: enabledCount.value, tone: 'cyan' },
  { key: 'disabled', label: '停用映射', value: disabledCount.value, tone: 'amber' }
])

async function load() {
  const params = { ...filters }
  if (params.entity_type === '') delete params.entity_type
  if (params.source_type === '') delete params.source_type
  if (params.is_active === '') delete params.is_active

  loading.value = true
  try {
    items.value = await fetchAliasMappings(params)
  } finally {
    loading.value = false
  }
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
  await ElMessageBox.confirm(`确认停用映射“${row.alias_code || row.alias_name || row.canonical_code}”吗？`, '提示', {
    type: 'warning'
  })
  await deleteAliasMapping(row.id)
  ElMessage.success('停用成功')
  await load()
}

onMounted(load)
</script>

<style scoped>
.alias-router {
  --alias-cyan: #00f2ff;
  --alias-cyan-soft: rgba(0, 242, 255, 0.12);
  --alias-amber: #ffab00;
  --alias-bg: rgba(1, 16, 31, 0.72);
  --alias-bg-strong: rgba(2, 12, 25, 0.92);
  --alias-line: rgba(0, 242, 255, 0.18);
  --alias-line-strong: rgba(0, 242, 255, 0.38);
  --alias-muted: rgba(185, 223, 235, 0.64);
  --alias-text: rgba(225, 253, 255, 0.94);
  position: relative;
  isolation: isolate;
  overflow-x: clip;
  color: var(--alias-text);
}

.alias-router::before {
  position: absolute;
  inset: -24px;
  z-index: -1;
  opacity: 0.42;
  background:
    linear-gradient(rgba(0, 242, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.06) 1px, transparent 1px),
    radial-gradient(circle at 84% 8%, rgba(0, 242, 255, 0.16), transparent 30%);
  background-size: 34px 34px, 34px 34px, auto;
  content: "";
  pointer-events: none;
}

.alias-router__hero,
.alias-router__scanbar,
.alias-router__matrix {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--alias-line);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(7, 36, 66, 0.82), rgba(1, 16, 31, 0.88)),
    var(--alias-bg);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 24px 62px rgba(0, 18, 42, 0.22);
}

.alias-router__hero::after,
.alias-router__scanbar::after,
.alias-router__matrix::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.1), transparent);
  opacity: 0.5;
  transform: translateX(-65%);
  animation: aliasRouterSweep 7s linear infinite;
  content: "";
  pointer-events: none;
}

.alias-router__hero {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(360px, 1.25fr) auto;
  gap: var(--xt-space-4);
  align-items: center;
  padding: var(--xt-space-5);
}

.alias-router__title-block {
  min-width: 0;
  display: grid;
  gap: var(--xt-space-2);
}

.alias-router__eyebrow,
.alias-router__matrix-head span,
.alias-router__stat span {
  color: #74f5ff;
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.12em;
}

.alias-router h1 {
  margin: 0;
  color: #e1fdff;
  font-family: var(--xt-font-display);
  font-size: clamp(30px, 4vw, 52px);
  font-weight: 950;
  letter-spacing: -0.035em;
  line-height: 0.96;
  text-shadow: 0 0 26px rgba(0, 242, 255, 0.18);
}

.alias-router__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.alias-router__stat {
  min-width: 0;
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-4);
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 14px;
  background: rgba(1, 12, 24, 0.76);
}

.alias-router__stat strong {
  color: #e1fdff;
  font-family: var(--xt-font-number);
  font-size: clamp(24px, 3vw, 34px);
  font-weight: 950;
  line-height: 1;
}

.alias-router__stat.is-cyan strong {
  color: var(--alias-cyan);
}

.alias-router__stat.is-amber strong {
  color: var(--alias-amber);
}

.alias-router__primary-action,
.alias-router__query {
  position: relative;
  overflow: hidden;
  border-color: rgba(0, 242, 255, 0.52);
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.94), rgba(0, 151, 178, 0.92)),
    var(--alias-cyan);
  color: #00282d;
  font-weight: 900;
  touch-action: manipulation;
}

.alias-router__primary-action::after,
.alias-router__query::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 22%, rgba(255, 255, 255, 0.42) 50%, transparent 76%);
  transform: translateX(-120%);
  transition: transform 360ms var(--xt-ease);
  content: "";
  pointer-events: none;
}

@media (hover: hover) {
  .alias-router__primary-action:hover::after,
  .alias-router__query:hover::after {
    transform: translateX(120%);
  }
}

.alias-router__scanbar {
  padding: var(--xt-space-4) var(--xt-space-4) 0;
}

.alias-router__filters {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-3);
  align-items: flex-end;
}

.alias-router__filters :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: var(--xt-space-4);
}

.alias-router__filters :deep(.el-form-item__label) {
  color: rgba(116, 245, 255, 0.78);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.08em;
}

.alias-router__filters :deep(.el-input__wrapper),
.alias-router__filters :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 10px;
  background: rgba(1, 10, 20, 0.72);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.28),
    inset 0 0 0 1px rgba(0, 242, 255, 0.16);
}

.alias-router__filters :deep(.el-input__inner),
.alias-router__filters :deep(.el-select__placeholder),
.alias-router__filters :deep(.el-select__selected-item) {
  color: var(--alias-text);
}

.alias-router__matrix {
  padding: var(--xt-space-4);
}

.alias-router__matrix-head {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  gap: var(--xt-space-4);
  align-items: end;
  margin-bottom: var(--xt-space-3);
}

.alias-router__matrix-head div {
  display: grid;
  gap: 4px;
}

.alias-router__matrix-head strong {
  color: #e1fdff;
  font-size: var(--xt-text-xl);
  font-weight: 950;
}

.alias-router__matrix-head small {
  color: var(--alias-muted);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-sm);
}

.alias-router__matrix-scroll {
  position: relative;
  z-index: 1;
  max-width: 100%;
  overflow-x: hidden;
  border-radius: 12px;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 242, 255, 0.42) transparent;
}

.alias-router :deep(.reference-data-table-shell) {
  max-width: 100%;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 242, 255, 0.42) transparent;
}

.alias-router :deep(.alias-router__table.el-table) {
  --el-bg-color: transparent;
  --el-fill-color-blank: transparent;
  --el-table-bg-color: transparent;
  --el-table-header-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-row-hover-bg-color: rgba(0, 242, 255, 0.1);
  --el-table-text-color: var(--alias-text);
  --el-table-header-text-color: rgba(185, 223, 235, 0.78);
  border-radius: 12px;
  background: rgba(1, 10, 20, 0.78);
  color: var(--alias-text);
  font-size: var(--xt-text-sm);
}

.alias-router :deep(.alias-router__table.el-table .el-table__header-wrapper),
.alias-router :deep(.alias-router__table.el-table .el-table__body-wrapper),
.alias-router :deep(.alias-router__table.el-table .el-table__fixed-right),
.alias-router :deep(.alias-router__table.el-table .el-table__fixed-right-patch) {
  background: transparent;
}

.alias-router :deep(.alias-router__table.el-table .el-table__inner-wrapper::before) {
  background: var(--alias-line);
}

.alias-router :deep(.alias-router__table.el-table th.el-table__cell),
.alias-router :deep(.alias-router__table.el-table tr),
.alias-router :deep(.alias-router__table.el-table td.el-table__cell) {
  background: transparent;
}

.alias-router :deep(.alias-router__table.el-table th.el-table__cell) {
  border-bottom: 1px solid var(--alias-line);
  color: rgba(116, 245, 255, 0.82);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.08em;
}

.alias-router :deep(.alias-router__table.el-table td.el-table__cell) {
  border-bottom: 1px solid rgba(0, 242, 255, 0.08);
}

.alias-router :deep(.alias-router__table.el-table .el-table__body tr:hover > td.el-table__cell) {
  background: rgba(0, 242, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(0, 242, 255, 0.05);
}

.alias-router__type-chip,
.alias-router__source,
.alias-router__status {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 999px;
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.alias-router__type-chip {
  padding: 0 var(--xt-space-2);
  border: 1px solid rgba(0, 242, 255, 0.18);
  background: rgba(0, 242, 255, 0.08);
  color: #dffcff;
}

.alias-router__source {
  color: rgba(185, 223, 235, 0.72);
  font-family: var(--xt-font-mono);
}

.alias-router__status {
  gap: 6px;
  color: #e1fdff;
}

.alias-router__status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--alias-cyan);
  box-shadow: 0 0 12px rgba(0, 242, 255, 0.82);
  animation: aliasRouterLed 1.8s ease-in-out infinite;
}

.alias-router__status.is-off {
  color: rgba(185, 223, 235, 0.54);
}

.alias-router__status.is-off i {
  background: #526679;
  box-shadow: none;
  animation: none;
}

.alias-router__mobile-list {
  position: relative;
  z-index: 1;
  display: none;
}

.alias-router__mobile-card {
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 12px;
  background: rgba(1, 10, 20, 0.78);
}

.alias-router__mobile-card header,
.alias-router__mobile-card footer,
.alias-router__mobile-type,
.alias-router__mobile-card dl div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
}

.alias-router__mobile-card header {
  color: rgba(185, 223, 235, 0.7);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.alias-router__mobile-type {
  justify-content: flex-start;
}

.alias-router__mobile-type strong {
  min-width: 0;
  overflow: hidden;
  color: #e1fdff;
  font-size: var(--xt-text-base);
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alias-router__mobile-card dl {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
}

.alias-router__mobile-card dl div {
  min-height: 32px;
  padding: 0 var(--xt-space-2);
  border-radius: 8px;
  background: rgba(0, 242, 255, 0.05);
}

.alias-router__mobile-card dt,
.alias-router__mobile-card dd {
  margin: 0;
}

.alias-router__mobile-card dt {
  color: rgba(116, 245, 255, 0.72);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.alias-router__mobile-card dd {
  min-width: 0;
  overflow: hidden;
  color: var(--alias-text);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alias-router__mobile-card footer {
  justify-content: flex-end;
  border-top: 1px solid rgba(0, 242, 255, 0.08);
  padding-top: var(--xt-space-2);
}

:deep(.alias-router__dialog .el-dialog) {
  border: 1px solid var(--alias-line, rgba(0, 242, 255, 0.18));
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(7, 36, 66, 0.96), rgba(2, 12, 25, 0.98)),
    #06101f;
  color: var(--alias-text, rgba(225, 253, 255, 0.94));
}

:deep(.alias-router__dialog .el-dialog__title),
:deep(.alias-router__dialog .el-form-item__label) {
  color: var(--alias-text, rgba(225, 253, 255, 0.94));
}

@keyframes aliasRouterSweep {
  0% { transform: translateX(-65%); opacity: 0; }
  18% { opacity: 0.45; }
  52% { opacity: 0.16; }
  100% { transform: translateX(65%); opacity: 0; }
}

@keyframes aliasRouterLed {
  0%, 100% { opacity: 0.72; transform: scale(0.92); }
  50% { opacity: 1; transform: scale(1.14); }
}

@media (max-width: 1180px) {
  .alias-router__hero {
    grid-template-columns: 1fr;
  }

  .alias-router__stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .alias-router__hero,
  .alias-router__scanbar,
  .alias-router__matrix {
    border-radius: 14px;
  }

  .alias-router__hero {
    padding: var(--xt-space-4);
  }

  .alias-router__stats {
    grid-template-columns: 1fr;
  }

  .alias-router__filters {
    display: grid;
  }

  .alias-router__filters :deep(.el-form-item) {
    display: grid;
  }

  .alias-router__filters :deep(.el-select),
  .alias-router__filters :deep(.el-input),
  .alias-router__query {
    width: 100% !important;
  }

  .alias-router__matrix {
    padding: var(--xt-space-3);
  }

  .alias-router__matrix-head {
    display: grid;
  }

  .alias-router__matrix-scroll {
    display: none;
  }

  .alias-router__mobile-list {
    display: grid;
    gap: var(--xt-space-3);
  }
}

@media (prefers-reduced-motion: reduce) {
  .alias-router__hero::after,
  .alias-router__scanbar::after,
  .alias-router__matrix::after,
  .alias-router__status i {
    animation: none;
  }

  .alias-router__primary-action::after,
  .alias-router__query::after {
    transition: none;
  }
}
</style>

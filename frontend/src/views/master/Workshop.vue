<template>
  <div class="page-stack workshop-master" data-testid="admin-master-center" title="车间主数据">
    <section class="workshop-master__hero" aria-labelledby="workshop-master-title">
      <div class="workshop-master__title-block">
        <span class="workshop-master__eyebrow">主数据总览</span>
        <h1 id="workshop-master-title">车间主数据</h1>
      </div>

      <div class="workshop-master__stats" aria-label="车间统计">
        <article
          v-for="stat in workshopStats"
          :key="stat.key"
          class="workshop-master__stat"
          :class="`is-${stat.tone}`"
        >
          <span>{{ stat.label }}</span>
          <strong>{{ stat.value }}</strong>
        </article>
      </div>

      <el-button class="workshop-master__primary-action" type="primary" @click="openCreate">
        新增车间
      </el-button>
    </section>

    <section class="workshop-master__nodes" data-testid="workshop-master-nodes" aria-label="车间节点">
      <article
        v-for="(workshop, index) in workshopVisuals"
        :key="workshop.key"
        class="workshop-master__node"
        :class="{ 'is-muted': !workshop.active }"
      >
        <span class="workshop-master__node-index">节点 {{ index + 1 }}</span>
        <XtWorkshopGlyph :workshop-type="workshop.type" :active="workshop.active" compact />
        <div class="workshop-master__node-main">
          <span>{{ workshop.code }}</span>
          <strong>{{ workshop.name }}</strong>
        </div>
        <span class="workshop-master__status" :class="{ 'is-off': !workshop.active }">
          <i aria-hidden="true"></i>
          {{ workshop.active ? '启用' : '停用' }}
        </span>
      </article>
    </section>

    <section class="workshop-master__matrix" data-testid="workshop-master-matrix">
      <header class="workshop-master__matrix-head">
        <div>
          <span>车间清单</span>
          <strong>车间清单</strong>
        </div>
        <small>{{ pageState.total }} 条记录</small>
      </header>

      <div class="workshop-master__matrix-scroll">
        <ReferenceDataTable
          :data="items"
          stripe
          v-loading="loading"
          class="workshop-master__table"
          data-testid="workshop-master-table"
        >
          <el-table-column prop="id" label="编号" width="80" />
          <el-table-column prop="code" label="编码" width="160" />
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="sort_order" label="排序" width="100" />
          <el-table-column prop="is_active" label="状态" width="110">
            <template #default="{ row }">
              <span class="workshop-master__status" :class="{ 'is-off': !row.is_active }">
                <i aria-hidden="true"></i>
                {{ row.is_active ? '启用' : '停用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button text type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </ReferenceDataTable>
      </div>

      <div class="workshop-master__mobile-list" data-testid="workshop-master-mobile-list">
        <article v-for="row in items" :key="row.id" class="workshop-master__mobile-card">
          <header>
            <span>{{ row.code || row.id }}</span>
            <span class="workshop-master__status" :class="{ 'is-off': !row.is_active }">
              <i aria-hidden="true"></i>
              {{ row.is_active ? '启用' : '停用' }}
            </span>
          </header>
          <strong>{{ row.name || '未命名车间' }}</strong>
          <dl>
            <div>
              <dt>编号</dt>
              <dd>{{ row.id }}</dd>
            </div>
            <div>
              <dt>排序</dt>
              <dd>{{ row.sort_order ?? 0 }}</dd>
            </div>
          </dl>
          <footer>
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" @click="remove(row)">删除</el-button>
          </footer>
        </article>
      </div>

      <div class="workshop-master__pagination table-pagination">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :current-page="currentPage"
          :page-size="pageState.limit"
          :total="pageState.total"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑车间' : '新增车间'" width="520px" class="workshop-master__dialog">
      <el-form ref="formRef" :model="form" :rules="workshopRules" label-width="100px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
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
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createWorkshop, deleteWorkshop, fetchWorkshopsPage, updateWorkshop } from '../../api/master.js'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import { XtWorkshopGlyph } from '../../components/xt'
import { normalizeWorkshopPayload } from '../../utils/workshopFormValidation.js'

const items = ref([])
const formRef = ref(null)
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
  code: '',
  name: '',
  sort_order: 0,
  is_active: true
})
const workshopRules = {
  code: [{ required: true, whitespace: true, message: '请输入车间编码', trigger: 'blur' }],
  name: [{ required: true, whitespace: true, message: '请输入车间名称', trigger: 'blur' }]
}

const currentPage = computed(() => Math.floor(pageState.skip / pageState.limit) + 1)
const activeCount = computed(() => items.value.filter((item) => item.is_active !== false).length)
const inactiveCount = computed(() => items.value.filter((item) => item.is_active === false).length)
const workshopStats = computed(() => [
  { key: 'total', label: '车间总数', value: pageState.total || items.value.length, tone: 'primary' },
  { key: 'active', label: '本页启用', value: activeCount.value, tone: 'cyan' },
  { key: 'inactive', label: '本页停用', value: inactiveCount.value, tone: 'amber' }
])
const workshopVisuals = computed(() => {
  const source = items.value.length
    ? items.value
    : [
        { code: 'ZD', name: '铸锭车间', is_active: true },
        { code: 'HR', name: '热轧车间', is_active: true },
        { code: 'CR', name: '冷轧车间', is_active: true },
        { code: 'LJ', name: '拉矫车间', is_active: true },
        { code: 'OA', name: '在线退火', is_active: true },
        { code: 'FG', name: '成品库', is_active: true }
      ]
  return source.slice(0, 8).map((item, index) => ({
    key: item.id || item.code || index,
    code: item.code || `W${index + 1}`,
    name: item.name || '未命名车间',
    active: item.is_active !== false,
    type: workshopTypeFromName(`${item.code || ''}${item.name || ''}`)
  }))
})

async function load() {
  loading.value = true
  try {
    const page = await fetchWorkshopsPage({
      skip: pageState.skip,
      limit: pageState.limit
    })
    items.value = page.items
    pageState.total = page.total
  } finally {
    loading.value = false
  }
}

function handlePageChange(page) {
  pageState.skip = (page - 1) * pageState.limit
  load()
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.sort_order = 0
  form.is_active = true
  editingId.value = null
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
  clearFormValidation()
}

function openEdit(row) {
  editingId.value = row.id
  form.code = row.code || ''
  form.name = row.name || ''
  form.sort_order = row.sort_order || 0
  form.is_active = row.is_active
  dialogVisible.value = true
  clearFormValidation()
}

async function save() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  const payload = normalizeWorkshopPayload(form)
  saving.value = true
  try {
    if (editingId.value) {
      await updateWorkshop(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createWorkshop(payload)
      ElMessage.success('新增成功')
      pageState.skip = 0
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function clearFormValidation() {
  nextTick(() => formRef.value?.clearValidate())
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除车间「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteWorkshop(row.id)
  ElMessage.success('删除成功')
  if (pageState.skip >= pageState.total - 1 && pageState.skip > 0) {
    pageState.skip = Math.max(0, pageState.skip - pageState.limit)
  }
  await load()
}

function workshopTypeFromName(name) {
  const value = String(name || '')
  if (/ZD|铸|熔|锭/i.test(value)) return 'casting'
  if (/HR|热轧|热/i.test(value)) return 'hot_roll'
  if (/CR|冷轧|冷/i.test(value)) return 'cold_roll'
  if (/LJ|拉矫|矫/i.test(value)) return 'leveling'
  if (/OA|退火/i.test(value)) return 'online_annealing'
  if (/FG|库|仓|成品/i.test(value)) return 'inventory'
  if (/跨|链路|调度/i.test(value)) return 'cross_workshop_flow'
  return 'finishing'
}

onMounted(load)
</script>

<style scoped>
.workshop-master {
  --workshop-cyan: var(--xt-primary);
  --workshop-cyan-soft: color-mix(in srgb, var(--xt-primary) 12%, transparent);
  --workshop-amber: var(--xt-warning);
  --workshop-bg: var(--xt-bg-page);
  --workshop-bg-strong: var(--xt-bg-panel-strong);
  --workshop-line: color-mix(in srgb, var(--xt-primary) 18%, transparent);
  --workshop-line-strong: color-mix(in srgb, var(--xt-primary) 38%, transparent);
  --workshop-muted: var(--xt-text-secondary);
  --workshop-text: var(--xt-text);
  position: relative;
  isolation: isolate;
  overflow-x: clip;
  color: var(--xt-text);
}

.workshop-master::before {
  position: absolute;
  inset: -24px;
  z-index: -1;
  opacity: 0.38;
  background: transparent;
  background-size: 34px 34px, 34px 34px, auto;
  content: "";
  pointer-events: none;
}

.workshop-master__hero,
.workshop-master__nodes,
.workshop-master__matrix {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;

}

.workshop-master__hero::after,
.workshop-master__nodes::after,
.workshop-master__matrix::after {
  position: absolute;
  inset: 0;
  background: transparent;
  opacity: 0.5;
  transform: translateX(-65%);

  content: "";
  pointer-events: none;
}

.workshop-master__hero {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(360px, 1.2fr) auto;
  gap: var(--xt-space-4);
  align-items: center;
  padding: var(--xt-space-5);
}

.workshop-master__title-block {
  min-width: 0;
  display: grid;
  gap: var(--xt-space-2);
}

.workshop-master__eyebrow,
.workshop-master__matrix-head span,
.workshop-master__stat span,
.workshop-master__node-index {
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  letter-spacing: 0.12em;
}

.workshop-master h1 {
  margin: 0;
  color: var(--xt-text);

  font-size: clamp(30px, 4vw, 52px);
  font-weight: 600;
  letter-spacing: -0.035em;
  line-height: 0.96;

}

.workshop-master__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.workshop-master__stat {
  min-width: 0;
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-4);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.workshop-master__stat strong {
  color: var(--xt-text);

  font-size: clamp(24px, 3vw, 34px);
  font-weight: 600;
  line-height: 1;
}

.workshop-master__stat.is-cyan strong {
  color: var(--xt-primary);
}

.workshop-master__stat.is-amber strong {
  color: var(--xt-warning);
}

.workshop-master__primary-action {
  position: relative;
  overflow: hidden;
  border-color: var(--xt-border);
  background: transparent;
  color: var(--xt-text);
  font-weight: 600;
  touch-action: manipulation;
}

.workshop-master__primary-action::after {
  position: absolute;
  inset: 0;
  background: transparent;
  transform: translateX(-120%);
  transition: transform 360ms var(--xt-ease);
  content: "";
  pointer-events: none;
}

@media (hover: hover) {
  .workshop-master__primary-action:hover::after {
    transform: translateX(120%);
  }
}

.workshop-master__nodes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(176px, 1fr));
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
}

.workshop-master__node {
  position: relative;
  z-index: 1;
  min-width: 0;
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.workshop-master__node::before {
  position: absolute;
  inset: auto 10px 0;
  height: 2px;
  background: transparent;
  content: "";

}

.workshop-master__node.is-muted {
  opacity: 0.62;
}

.workshop-master__node :deep(.xt-workshop-glyph) {
  min-height: 70px;
}

.workshop-master__node-main {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.workshop-master__node-main span {
  color: var(--xt-warning);

  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.workshop-master__node-main strong,
.workshop-master__mobile-card strong {
  min-width: 0;
  overflow: hidden;
  color: var(--xt-text);
  font-size: var(--xt-text-base);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workshop-master__matrix {
  padding: var(--xt-space-4);
}

.workshop-master__matrix-head {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  gap: var(--xt-space-4);
  align-items: end;
  margin-bottom: var(--xt-space-3);
}

.workshop-master__matrix-head div {
  display: grid;
  gap: 4px;
}

.workshop-master__matrix-head strong {
  color: var(--xt-text);
  font-size: var(--xt-text-xl);
  font-weight: 600;
}

.workshop-master__matrix-head small {
  color: var(--xt-text-secondary);

  font-size: var(--xt-text-sm);
}

.workshop-master__matrix-scroll {
  position: relative;
  z-index: 1;
  max-width: 100%;
  overflow-x: hidden;
  border-radius: 4px;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--xt-primary) 42%, transparent) transparent;
}

.workshop-master :deep(.reference-data-table-shell) {
  max-width: 100%;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--xt-primary) 42%, transparent) transparent;
}

.workshop-master :deep(.workshop-master__table.el-table) {
  --el-bg-color: transparent;
  --el-fill-color-blank: transparent;
  --el-table-bg-color: transparent;
  --el-table-text-color: var(--workshop-text);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}

.workshop-master :deep(.workshop-master__table.el-table .el-table__header-wrapper),
.workshop-master :deep(.workshop-master__table.el-table .el-table__body-wrapper),
.workshop-master :deep(.workshop-master__table.el-table .el-table__fixed-right),
.workshop-master :deep(.workshop-master__table.el-table .el-table__fixed-right-patch) {
  background: transparent;
}

.workshop-master :deep(.workshop-master__table.el-table .el-table__inner-wrapper::before) {
  background: transparent;
}

.workshop-master :deep(.workshop-master__table.el-table .el-table__inner-wrapper::after),
.workshop-master :deep(.workshop-master__table.el-table .el-table__border-left-patch) {
  background: transparent;
}

.workshop-master :deep(.workshop-master__table.el-table th.el-table__cell),
.workshop-master :deep(.workshop-master__table.el-table tr),
.workshop-master :deep(.workshop-master__table.el-table td.el-table__cell) {
  background: transparent;
}

.workshop-master :deep(.workshop-master__table.el-table th.el-table__cell) {
  border-bottom: 1px solid var(--xt-border);
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
}

.workshop-master :deep(.workshop-master__table.el-table td.el-table__cell) {
  border-bottom: 1px solid var(--xt-border);
}

.workshop-master :deep(.workshop-master__table.el-table .el-table__body tr:hover > td.el-table__cell) {
  background: transparent;

}

.workshop-master__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.workshop-master__status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: transparent;


}

.workshop-master__status.is-off {
  color: var(--xt-text-secondary);
}

.workshop-master__status.is-off i {
  background: transparent;

  animation: none;
}

.workshop-master__mobile-list {
  position: relative;
  z-index: 1;
  display: none;
}

.workshop-master__mobile-card {
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.workshop-master__mobile-card header,
.workshop-master__mobile-card footer,
.workshop-master__mobile-card dl div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
}

.workshop-master__mobile-card header {
  color: var(--xt-text-secondary);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.workshop-master__mobile-card dl {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
}

.workshop-master__mobile-card dl div {
  min-height: 32px;
  padding: 0 var(--xt-space-2);
  border-radius: 4px;
  background: transparent;
}

.workshop-master__mobile-card dt,
.workshop-master__mobile-card dd {
  margin: 0;
}

.workshop-master__mobile-card dt {
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.workshop-master__mobile-card dd {
  color: var(--xt-text);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.workshop-master__mobile-card footer {
  justify-content: flex-end;
  border-top: 1px solid var(--xt-border);
  padding-top: var(--xt-space-2);
}

.workshop-master__pagination {
  position: relative;
  z-index: 1;
  margin-top: var(--xt-space-4);
}

.workshop-master__pagination :deep(.el-pagination) {
  justify-content: flex-end;
}

:deep(.workshop-master__dialog .el-dialog) {
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text);
}

:deep(.workshop-master__dialog .el-dialog__title),
:deep(.workshop-master__dialog .el-form-item__label) {
  color: var(--xt-text);
}

@keyframes workshopMasterSweep {
  0% { transform: translateX(-65%); opacity: 0; }
  18% { opacity: 0.45; }
  52% { opacity: 0.16; }
  100% { transform: translateX(65%); opacity: 0; }
}

@keyframes workshopMasterLed {
  0%, 100% { opacity: 0.72; transform: scale(0.92); }
  50% { opacity: 1; transform: scale(1.14); }
}

@media (max-width: 1180px) {
  .workshop-master__hero {
    grid-template-columns: 1fr;
  }

  .workshop-master__stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .workshop-master__hero,
  .workshop-master__nodes,
  .workshop-master__matrix {
    border-radius: 4px;
  }

  .workshop-master__hero {
    padding: var(--xt-space-4);
  }

  .workshop-master__stats,
  .workshop-master__nodes {
    grid-template-columns: 1fr;
  }

  .workshop-master__matrix {
    padding: var(--xt-space-3);
  }

  .workshop-master__matrix-head {
    display: grid;
  }

  .workshop-master__matrix-scroll {
    display: none;
  }

  .workshop-master__mobile-list {
    display: grid;
    gap: var(--xt-space-3);
  }

  .workshop-master__pagination :deep(.el-pagination) {
    justify-content: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workshop-master__hero::after,
  .workshop-master__nodes::after,
  .workshop-master__matrix::after,
  .workshop-master__node::before,
  .workshop-master__status i {
    animation: none;
  }

  .workshop-master__primary-action::after {
    transition: none;
  }
}
</style>

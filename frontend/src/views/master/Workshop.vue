<template>
  <ReferencePageFrame
    module-number="14"
    title="主数据与模板中心"
    :tags="['车间主数据', '班组员工', '机台班次']"
    class="page-stack admin-master-center"
    data-testid="admin-master-center"
  >
    <template #actions>
      <el-button type="primary" @click="openCreate">新增车间</el-button>
    </template>

    <section class="admin-master-center__workshops">
      <article
        v-for="workshop in workshopVisuals"
        :key="workshop.key"
        class="admin-master-center__workshop-card"
        :class="{ 'is-muted': !workshop.active }"
      >
        <XtWorkshopGlyph :workshop-type="workshop.type" :active="workshop.active" compact />
        <div>
          <span>{{ workshop.code }}</span>
          <strong>{{ workshop.name }}</strong>
        </div>
      </article>
    </section>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe v-loading="loading">
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="code" label="编码" width="160" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="sort_order" label="排序" width="100" />
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑车间' : '新增车间'" width="520px">
      <el-form :model="form" label-width="100px">
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
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createWorkshop, deleteWorkshop, fetchWorkshopsPage, updateWorkshop } from '../../api/master.js'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { XtWorkshopGlyph } from '../../components/xt'

const items = ref([])
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

const currentPage = computed(() => Math.floor(pageState.skip / pageState.limit) + 1)
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
}

function openEdit(row) {
  editingId.value = row.id
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
      await updateWorkshop(editingId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createWorkshop({ ...form })
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
.admin-master-center__workshops {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(154px, 1fr));
  gap: var(--xt-space-3);
}

.admin-master-center__workshop-card {
  min-width: 0;
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.admin-master-center__workshop-card :deep(.xt-workshop-glyph) {
  min-height: 64px;
}

.admin-master-center__workshop-card div {
  display: grid;
  gap: 2px;
}

.admin-master-center__workshop-card span {
  color: var(--xt-accent);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.admin-master-center__workshop-card strong {
  overflow: hidden;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-master-center__workshop-card.is-muted {
  opacity: 0.58;
}
</style>

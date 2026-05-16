<template>
  <section class="settings-center page-stack">
    <header class="page-header">
      <h1>系统配置中心</h1>
    </header>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="基础参数" name="params">
        <XtSectionCard title="系统参数">
          <XtSkeleton v-if="loading" :rows="5" />
          <XtDataTable
            v-else
            :columns="paramColumns"
            :data="params"
            :striped="true"
            :compact="true"
            data-source="system_config"
          />
          <XtEmpty v-if="!loading && !params.length" text="暂无配置参数" />
        </XtSectionCard>
      </el-tab-pane>

      <el-tab-pane label="口径配置" name="calibration">
        <XtSectionCard title="计算口径">
          <XtSkeleton v-if="loading" :rows="5" />
          <XtDataTable
            v-else
            :columns="calibrationColumns"
            :data="calibrations"
            :striped="true"
            :compact="true"
            data-source="calibration_config"
          />
          <XtEmpty v-if="!loading && !calibrations.length" text="暂无口径配置" />
        </XtSectionCard>
      </el-tab-pane>

      <el-tab-pane label="班次配置" name="shifts">
        <XtSectionCard title="班次定义">
          <XtSkeleton v-if="loading" :rows="3" />
          <XtDataTable
            v-else
            :columns="shiftColumns"
            :data="shifts"
            :striped="true"
            data-source="shift_config"
          />
          <XtEmpty v-if="!loading && !shifts.length" text="暂无班次配置" />
        </XtSectionCard>
      </el-tab-pane>

      <el-tab-pane label="产品配置" name="products">
        <XtSectionCard title="产品目录">
          <XtSkeleton v-if="loading" :rows="5" />
          <XtDataTable
            v-else
            :columns="productColumns"
            :data="products"
            :striped="true"
            data-source="product_config"
          />
          <XtEmpty v-if="!loading && !products.length" text="暂无产品配置" />
        </XtSectionCard>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { api } from '../../api/index'
import XtSectionCard from '../../components/xt/XtSectionCard.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'

const activeTab = ref('params')
const loading = ref(false)
const params = ref([])
const calibrations = ref([])
const shifts = ref([])
const products = ref([])

const paramColumns = [
  { key: 'key', label: '参数名', width: '200px' },
  { key: 'value', label: '当前值', width: '160px' },
  { key: 'unit', label: '单位', width: '80px' },
  { key: 'scope', label: '作用域', width: '120px' },
  { key: 'updated_at', label: '更新时间', width: '160px' }
]

const calibrationColumns = [
  { key: 'name', label: '口径名称', width: '180px' },
  { key: 'formula', label: '计算公式', width: '240px' },
  { key: 'source', label: '数据来源', width: '140px' },
  { key: 'updated_at', label: '更新时间', width: '160px' }
]

const shiftColumns = [
  { key: 'name', label: '班次名称', width: '120px' },
  { key: 'start_time', label: '开始时间', width: '100px' },
  { key: 'end_time', label: '结束时间', width: '100px' },
  { key: 'workshop_name', label: '适用车间', width: '140px' }
]

const productColumns = [
  { key: 'code', label: '产品编码', width: '120px' },
  { key: 'name', label: '产品名称', width: '160px' },
  { key: 'category', label: '分类', width: '100px' },
  { key: 'unit', label: '单位', width: '80px' },
  { key: 'status', label: '状态', width: '80px' }
]

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/settings/all')
    params.value = data.params || []
    calibrations.value = data.calibrations || []
    shifts.value = data.shifts || []
    products.value = data.products || []
  } catch {
    // silent — individual tabs show empty state
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-center {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-6);
}

.page-header {
  display: flex;
  align-items: center;
  gap: var(--xt-space-4);
}

.page-header h1 {
  font-size: var(--xt-text-xl);
  font-weight: 700;
  margin: 0;
}
</style>

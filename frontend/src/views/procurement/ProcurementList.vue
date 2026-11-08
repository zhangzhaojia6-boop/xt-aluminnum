<template>
  <section class="pc-list" data-testid="procurement-list">
    <header class="pc-list__head">
      <h1>{{ scope === 'mine' ? '我提报的' : '待我办理' }}</h1>
      <RouterLink class="pc-list__new" to="/procurement/new" data-testid="procurement-new">提报需求</RouterLink>
    </header>

    <p v-if="loading" class="pc-list__state" role="status">加载中</p>
    <div v-else-if="failed" class="pc-list__state">
      读取失败
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="!rows.length" class="pc-list__empty">
      <XtCoilMark />
      <span>{{ scope === 'mine' ? '还没有提报过' : '当前没有要办的' }}</span>
    </div>

    <ul v-else class="pc-list__rows">
      <li v-for="row in rows" :key="row.id">
        <RouterLink :to="`/procurement/${row.id}`" data-testid="procurement-row">
          <span class="pc-list__main">
            <strong>{{ row.material_name }}</strong>
            <small>{{ row.request_no }} · {{ row.quantity }}{{ row.unit }} · ¥{{ row.amount }}</small>
          </span>
          <span class="pc-list__step" :class="{ 'is-overdue': row.is_overdue }">
            {{ statusLabel(row) }}
            <small v-if="row.is_overdue">已超时</small>
            <small v-else-if="row.is_emergency">紧急</small>
          </span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { fetchProcurementRequests } from '../../api/procurement.js'
import XtCoilMark from '../../components/xt/XtCoilMark.vue'

const props = defineProps({ scope: { type: String, default: 'todo' } })

const STATUS_LABELS = { archived: '已归档', closed_stock: '库存充足，已驳回', cancelled: '已撤销' }
const rows = ref([])
const loading = ref(true)
const failed = ref(false)

function statusLabel(row) {
  return STATUS_LABELS[row.status] || `${row.step_number}. ${row.step_label}`
}

async function load() {
  loading.value = true
  failed.value = false
  try {
    rows.value = await fetchProcurementRequests(props.scope)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pc-list__head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.pc-list__head h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-list__new { display: inline-flex; align-items: center; min-height: 48px; padding: 0 20px; border-radius: 4px; background: var(--xt-primary); color: #fff; font-weight: 600; text-decoration: none; }
.pc-list__state { padding: 40px 0; color: var(--xt-text-secondary); text-align: center; }
.pc-list__state button { min-height: 44px; margin-left: 12px; padding: 0 16px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); font: inherit; cursor: pointer; }
.pc-list__empty { display: grid; justify-items: center; gap: 16px; padding: 64px 0; color: var(--xt-text-muted); }
.pc-list__rows { margin: 0; padding: 0; list-style: none; }
.pc-list__rows a { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 72px; padding: 12px 0; border-bottom: 1px solid var(--xt-border); color: var(--xt-text); text-decoration: none; }
.pc-list__main { display: grid; gap: 4px; min-width: 0; }
.pc-list__main strong { font-size: 16px; font-weight: 600; }
.pc-list__main small { color: var(--xt-text-muted); font-size: 14px; font-variant-numeric: tabular-nums; }
.pc-list__step { display: grid; flex: none; gap: 2px; color: var(--xt-primary); text-align: right; }
.pc-list__step small { color: var(--xt-warning); font-size: 12px; }
.pc-list__step.is-overdue small { color: var(--xt-danger); }
</style>

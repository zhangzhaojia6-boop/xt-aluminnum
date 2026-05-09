<template>
  <section class="pf-root">
    <header class="pf-head">
      <div>
        <h1>加工费管理</h1>
        <span class="pf-sub">牌号 × 工艺 × 状态 × 厚度 → 加工费/吨（含税）</span>
      </div>
      <div class="pf-actions">
        <select v-model="tierFilter" class="pf-sel" @change="reload">
          <option value="">全部客户</option>
          <option value="default">default（客户A）</option>
          <option value="hengchang">hengchang（巩义恒昌）</option>
        </select>
        <button class="pf-btn" @click="openCreate">新增规则</button>
      </div>
    </header>

    <div class="pf-card">
      <table class="pf-table">
        <thead>
          <tr>
            <th>客户分层</th>
            <th>牌号</th>
            <th>工艺</th>
            <th>状态</th>
            <th>厚度区间 (mm)</th>
            <th>加工费/吨</th>
            <th>生效</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length"><td colspan="8" class="pf-empty">暂无规则</td></tr>
          <tr v-for="r in rows" :key="r.id">
            <td><span class="pf-tier" :class="r.customer_tier">{{ r.customer_tier }}</span></td>
            <td><strong>{{ r.alloy_grade }}</strong></td>
            <td>{{ processLabel(r.process_type) }}</td>
            <td>{{ r.temper || '—' }}</td>
            <td>
              <span v-if="r.thickness_min_mm !== null || r.thickness_max_mm !== null">
                {{ r.thickness_min_mm ?? '0' }} ~ {{ r.thickness_max_mm ?? '∞' }}
              </span>
              <span v-else class="pf-dim">全部</span>
            </td>
            <td><strong>¥{{ r.fee_per_ton.toLocaleString('zh-CN') }}</strong></td>
            <td class="pf-dim">{{ r.effective_from }}</td>
            <td>
              <button class="pf-link" @click="openEdit(r)">编辑</button>
              <button class="pf-link danger" @click="confirmDelete(r)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="editing" class="pf-modal" @click.self="editing = null">
      <div class="pf-modal-body">
        <h2>{{ editing.id ? '编辑加工费规则' : '新增加工费规则' }}</h2>
        <div class="pf-form">
          <label>客户分层<input v-model="editing.customer_tier" placeholder="default / hengchang" /></label>
          <label>牌号<input v-model="editing.alloy_grade" placeholder="5052 / 6061 ..." /></label>
          <label>工艺
            <select v-model="editing.process_type">
              <option value="cold_rolling">冷轧 cold_rolling</option>
              <option value="hot_rolling">热轧 hot_rolling</option>
              <option value="new_process">新工艺 new_process</option>
              <option value="casting_rolling">铸轧 casting_rolling</option>
              <option value="extrusion">挤压 extrusion</option>
            </select>
          </label>
          <label>状态（temper）<input v-model="editing.temper" placeholder="H32/O / T6/T4 / O ..." /></label>
          <label>厚度下限 (mm)<input type="number" step="0.1" v-model.number="editing.thickness_min_mm" /></label>
          <label>厚度上限 (mm)<input type="number" step="0.1" v-model.number="editing.thickness_max_mm" /></label>
          <label>加工费 (含税, 元/吨)<input type="number" step="1" v-model.number="editing.fee_per_ton" /></label>
          <label>生效日期<input type="date" v-model="editing.effective_from" /></label>
          <label>失效日期 (可空)<input type="date" v-model="editing.effective_to" /></label>
          <label class="pf-note">备注<textarea v-model="editing.note" rows="2"></textarea></label>
        </div>
        <div class="pf-modal-actions">
          <button class="pf-btn ghost" @click="editing = null">取消</button>
          <button class="pf-btn" @click="save" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  fetchProcessingFees,
  createProcessingFee,
  updateProcessingFee,
  deleteProcessingFee,
} from '../../api/executive'

const rows = ref([])
const tierFilter = ref('')
const editing = ref(null)
const saving = ref(false)

function processLabel(p) {
  return {
    cold_rolling: '冷轧',
    hot_rolling: '热轧',
    new_process: '新工艺',
    casting_rolling: '铸轧',
    extrusion: '挤压',
  }[p] || p
}

async function reload() {
  const params = tierFilter.value ? { customer_tier: tierFilter.value } : {}
  rows.value = await fetchProcessingFees(params)
}

function openCreate() {
  editing.value = {
    customer_tier: 'default',
    alloy_grade: '',
    process_type: 'hot_rolling',
    temper: '',
    thickness_min_mm: null,
    thickness_max_mm: null,
    fee_per_ton: 0,
    is_vat_inclusive: true,
    effective_from: new Date().toISOString().slice(0, 10),
    effective_to: null,
    note: '',
  }
}

function openEdit(r) {
  editing.value = { ...r }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...editing.value }
    if (payload.temper === '') payload.temper = null
    if (payload.note === '') payload.note = null
    if (payload.id) {
      await updateProcessingFee(payload.id, payload)
    } else {
      await createProcessingFee(payload)
    }
    editing.value = null
    await reload()
  } finally {
    saving.value = false
  }
}

async function confirmDelete(r) {
  if (!window.confirm(`确认删除 ${r.alloy_grade} / ${r.process_type} / ${r.temper || '-'} 的加工费规则？`)) return
  await deleteProcessingFee(r.id)
  await reload()
}

onMounted(reload)
</script>

<style scoped>
.pf-root {
  min-height: 100vh;
  padding: 20px clamp(16px, 3vw, 40px);
  background: oklch(12% 0.015 252);
  color: oklch(92% 0.01 252);
  font-variant-numeric: tabular-nums;
}
.pf-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid oklch(28% 0.03 252);
}
.pf-head h1 { margin: 0; font-size: 20px; font-weight: 900; }
.pf-sub { color: oklch(58% 0.02 252); font-size: 13px; font-weight: 800; }
.pf-actions { display: flex; gap: 8px; }
.pf-sel, .pf-btn {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  font-weight: 850;
}
.pf-sel {
  border: 1px solid oklch(30% 0.03 252);
  background: oklch(16% 0.018 252);
  color: oklch(92% 0.01 252);
}
.pf-btn {
  border: 0;
  background: oklch(62% 0.18 255);
  color: #fff;
  cursor: pointer;
}
.pf-btn.ghost {
  background: transparent;
  border: 1px solid oklch(30% 0.03 252);
  color: oklch(92% 0.01 252);
}
.pf-card {
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 10px;
  background: oklch(18% 0.022 252);
  overflow: hidden;
}
.pf-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pf-table th, .pf-table td {
  padding: 10px 14px;
  border-bottom: 1px solid oklch(25% 0.03 252);
  text-align: left;
}
.pf-table th {
  background: oklch(16% 0.02 252);
  color: oklch(58% 0.02 252);
  font-weight: 850;
  font-size: 12px;
  letter-spacing: 0.5px;
}
.pf-empty { text-align: center; color: oklch(58% 0.02 252); padding: 28px; }
.pf-tier {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: oklch(25% 0.06 255);
  color: oklch(80% 0.12 255);
  font-size: 11px;
  font-weight: 850;
}
.pf-tier.hengchang {
  background: oklch(25% 0.08 75);
  color: oklch(80% 0.12 75);
}
.pf-dim { color: oklch(58% 0.02 252); }
.pf-link {
  background: transparent;
  border: 0;
  color: oklch(72% 0.14 255);
  font-weight: 800;
  cursor: pointer;
  padding: 0 6px;
}
.pf-link.danger { color: oklch(72% 0.16 28); }

.pf-modal {
  position: fixed; inset: 0;
  background: oklch(8% 0.01 252 / 0.85);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
}
.pf-modal-body {
  width: min(620px, 90vw);
  max-height: 90vh;
  overflow: auto;
  padding: 24px;
  border-radius: 12px;
  background: oklch(18% 0.022 252);
  border: 1px solid oklch(30% 0.03 252);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.pf-modal-body h2 { margin: 0 0 18px; font-size: 16px; font-weight: 900; }
.pf-form { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.pf-form label { display: grid; gap: 4px; font-size: 12px; color: oklch(58% 0.02 252); font-weight: 800; }
.pf-form input, .pf-form select, .pf-form textarea {
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid oklch(30% 0.03 252);
  border-radius: 6px;
  background: oklch(14% 0.015 252);
  color: oklch(92% 0.01 252);
  font-variant-numeric: tabular-nums;
}
.pf-form textarea { padding: 8px 10px; min-height: 60px; }
.pf-form .pf-note { grid-column: span 2; }
.pf-modal-actions {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

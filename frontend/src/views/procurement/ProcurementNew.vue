<template>
  <form class="pc-new" data-testid="procurement-form" @submit.prevent="save">
    <h1>提报需求</h1>

    <label class="pc-new__field">物料名称<input v-model.trim="form.material_name" required maxlength="128" data-testid="pc-material" /></label>
    <label class="pc-new__field">规格型号<input v-model.trim="form.specification" maxlength="128" /></label>

    <fieldset class="pc-new__field">
      <legend>物资类别</legend>
      <div class="pc-new__chips">
        <label v-for="item in categories" :key="item" :class="{ 'is-on': form.category === item }">
          <input v-model="form.category" type="radio" name="category" :value="item" required />{{ item }}
        </label>
      </div>
    </fieldset>

    <div class="pc-new__row">
      <label class="pc-new__field">数量<input v-model="form.quantity" type="number" inputmode="decimal" step="any" min="0" required data-testid="pc-quantity" /></label>
      <label class="pc-new__field">单位<input v-model.trim="form.unit" required maxlength="16" data-testid="pc-unit" /></label>
    </div>
    <div class="pc-new__row">
      <label class="pc-new__field">预估单价（元）<input v-model="form.estimated_unit_price" type="number" inputmode="decimal" step="any" min="0" required data-testid="pc-price" /></label>
      <label class="pc-new__field">需求到货日期<input v-model="form.needed_by" type="date" /></label>
    </div>
    <label class="pc-new__field">用途<textarea v-model.trim="form.purpose" rows="2" required data-testid="pc-purpose" /></label>

    <label class="pc-new__check"><input v-model="form.is_emergency" type="checkbox" />生产线紧急抢修</label>

    <div class="pc-new__total">
      <span>预估总金额</span>
      <b data-testid="pc-total">¥{{ totalText }}</b>
    </div>

    <p v-if="error" class="pc-new__error" role="alert">{{ error }}</p>
    <button class="pc-new__submit" type="submit" :disabled="saving" data-testid="pc-save">{{ saving ? '保存中' : '保存，下一步提交' }}</button>
  </form>
</template>

<script setup>
import { computed, inject, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createProcurementRequest } from '../../api/procurement.js'
import { formatApiErrorMessage } from '../../api/index.js'

const router = useRouter()
const meta = inject('procurementMeta')
const categories = computed(() => meta.value.categories || [])
const saving = ref(false)
const error = ref('')
const form = reactive({
  material_name: '',
  specification: '',
  category: '',
  quantity: '',
  unit: '',
  estimated_unit_price: '',
  needed_by: '',
  purpose: '',
  is_emergency: false,
})

const totalText = computed(() => {
  const total = Number(form.quantity) * Number(form.estimated_unit_price)
  return Number.isFinite(total) ? total.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : '-'
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    const created = await createProcurementRequest({ ...form, needed_by: form.needed_by || null })
    await router.replace(`/procurement/${created.id}`)
  } catch (err) {
    error.value = formatApiErrorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.pc-new { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; max-width: 600px; }
.pc-new h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-new__field { display: grid; gap: 8px; min-width: 0; margin: 0; padding: 0; border: 0; color: var(--xt-text-secondary); font-size: 14px; }
.pc-new__field legend { margin-bottom: 8px; padding: 0; }
.pc-new__field input, .pc-new__field textarea { box-sizing: border-box; width: 100%; min-width: 0; min-height: 52px; padding: 0 12px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; font-size: 18px; }
.pc-new__field textarea { padding: 12px 14px; }
.pc-new__row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.pc-new__chips { display: flex; flex-wrap: wrap; gap: 8px; }
.pc-new__chips label { display: inline-flex; align-items: center; min-height: 44px; padding: 0 14px; border: 1px solid var(--xt-border); border-radius: 4px; color: var(--xt-text); cursor: pointer; }
.pc-new__chips label.is-on { border-color: var(--xt-primary); background: var(--xt-primary-light); color: var(--xt-primary); font-weight: 600; }
.pc-new__chips input { position: absolute; opacity: 0; width: 1px; height: 1px; }
.pc-new__chips label:focus-within { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
.pc-new__check { display: flex; align-items: center; gap: 10px; min-height: 44px; }
.pc-new__check input { width: 20px; height: 20px; }
.pc-new__total { display: flex; align-items: baseline; justify-content: space-between; padding: 16px 0; border-block: 1px solid var(--xt-border); color: var(--xt-text-secondary); }
.pc-new__total b { color: var(--xt-text); font-size: 28px; font-weight: 600; font-variant-numeric: tabular-nums; }
.pc-new__error { margin: 0; color: var(--xt-danger); }
.pc-new__submit { min-height: 56px; border: 0; border-radius: 4px; background: var(--xt-primary-solid, var(--xt-primary)); color: #fff; font: inherit; font-size: 18px; font-weight: 600; cursor: pointer; }
.pc-new__submit:disabled { background: var(--xt-bg-depth); color: var(--xt-text-muted); cursor: default; }
</style>

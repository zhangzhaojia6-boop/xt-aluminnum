<template>
  <div class="cmd-page cmd-entry-terminal-page" data-module="03" data-testid="mobile-entry">
    <section class="cmd-entry-terminal">
      <img class="cmd-entry-terminal__visual" :src="entryTerminalImage" alt="" />
      <div class="cmd-entry-terminal__functional">
        <header class="cmd-module-page__head">
          <div class="cmd-module-page__title">
            <span class="cmd-module-page__number">03</span>
            <h1>独立填报终端首页</h1>
          </div>
          <span class="cmd-status" data-testid="mobile-current-shift">当前班次 {{ currentShiftLabel }}</span>
        </header>
        <div data-testid="mobile-role-bucket" class="cmd-status">现场直接报数</div>
        <button type="button" class="cmd-button is-primary" data-testid="mobile-go-report" @click="openAdvancedForm">
          快速填报
        </button>
        <button type="button">高质填报</button>
        <button type="button">拍照识别</button>
        <button type="button">历史记录</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../../api/index.js'
import entryTerminalImage from '../assets/entry-terminal.png'

const router = useRouter()
const currentShift = ref(null)
const currentShiftLabel = computed(() => currentShift.value?.shift_name || currentShift.value?.name || '白班')

function resolveShiftParam(key, fallback) {
  return currentShift.value?.[key] || currentShift.value?.current_shift?.[key] || fallback
}

function openAdvancedForm() {
  const businessDate = resolveShiftParam('business_date', new Date().toISOString().slice(0, 10))
  const shiftId = resolveShiftParam('shift_id', 1)
  router.push(`/entry/advanced/${businessDate}/${shiftId}`)
}

onMounted(async () => {
  try {
    const { data } = await api.get('/mobile/current-shift', { skipErrorToast: true })
    currentShift.value = data
  } catch {
    currentShift.value = { shift_name: '白班' }
  }
})
</script>

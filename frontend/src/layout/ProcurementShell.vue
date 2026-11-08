<template>
  <div class="pc-shell" data-testid="procurement-shell">
    <header class="pc-shell__top">
      <RouterLink class="pc-shell__brand" to="/procurement">
        <XtLogo variant="icon" />
        <span>物资采购</span>
      </RouterLink>
      <RouterLink v-if="!auth.isProcurementOnly" class="pc-shell__back" :to="homePath">返回</RouterLink>
    </header>

    <nav v-if="enabled" class="pc-shell__tabs" aria-label="采购导航">
      <RouterLink to="/procurement" :class="{ 'is-active': route.path === '/procurement' }">待我办理</RouterLink>
      <RouterLink to="/procurement/mine" :class="{ 'is-active': route.path === '/procurement/mine' }">我提报的</RouterLink>
      <RouterLink v-if="canViewAll" to="/procurement/board" :class="{ 'is-active': route.path === '/procurement/board' }">台账</RouterLink>
    </nav>

    <main class="pc-shell__body">
      <div v-if="enabled === false" class="pc-shell__off" data-testid="procurement-disabled">
        <XtCoilMark />
        <strong>采购模块尚未开启</strong>
      </div>
      <RouterView v-else-if="enabled" />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { fetchProcurementMeta } from '../api/procurement.js'
import { XtLogo } from '../components/xt'
import XtCoilMark from '../components/xt/XtCoilMark.vue'
import { useAuthStore } from '../stores/auth.js'

const route = useRoute()
const auth = useAuthStore()
const enabled = ref(null)
const meta = ref({})

provide('procurementMeta', meta)

const canViewAll = computed(() => Boolean(meta.value.can_view_all))
const homePath = computed(() => {
  if (auth.isWorkshopDirector) return '/manage/workshop-dashboard'
  return auth.canAccessReviewSurface ? '/manage/today' : '/entry'
})

onMounted(async () => {
  try {
    meta.value = await fetchProcurementMeta()
    enabled.value = true
  } catch {
    enabled.value = false
  }
})
</script>

<style scoped>
.pc-shell { min-height: 100dvh; max-width: 980px; margin: 0 auto; background: var(--xt-bg-page); color: var(--xt-text); overflow-wrap: anywhere; }
.pc-shell__top { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; min-height: 56px; padding: 8px 20px; border-bottom: 1px solid var(--xt-border); background: var(--xt-bg-page); }
.pc-shell__brand { display: inline-flex; align-items: center; gap: 8px; color: var(--xt-text); font-weight: 600; text-decoration: none; }
.pc-shell__brand :deep(.xt-logo__icon) { width: 28px; height: 28px; }
.pc-shell__back { display: inline-flex; align-items: center; min-height: 44px; color: var(--xt-text-secondary); text-decoration: none; }
.pc-shell__tabs { display: flex; gap: 24px; padding: 0 20px; border-bottom: 1px solid var(--xt-border); }
.pc-shell__tabs a { display: flex; align-items: center; min-height: 48px; color: var(--xt-text-secondary); text-decoration: none; }
.pc-shell__tabs a.is-active { box-shadow: inset 0 -2px 0 var(--xt-primary); color: var(--xt-primary); font-weight: 600; }
.pc-shell__body { padding: 24px 20px 64px; }
.pc-shell__off { display: grid; justify-items: center; gap: 16px; padding: 80px 0; color: var(--xt-text-secondary); }
</style>

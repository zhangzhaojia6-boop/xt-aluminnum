<template>
  <div class="app-entry-shell" data-testid="entry-shell">
    <header class="app-entry-shell__topbar">
      <div>
        <p class="app-entry-shell__title">独立填报端</p>
        <p class="app-entry-shell__subtitle">主操 / 班组长 / 专项负责人</p>
      </div>
      <nav class="app-entry-shell__nav" aria-label="录入端导航">
        <button
          v-for="item in navItems"
          :key="item.routeName"
          type="button"
          :class="{ 'is-active': route.name === item.routeName }"
          @click="go(item.routeName)"
        >
          {{ item.label }}
        </button>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const navItems = [
  { routeName: 'mobile-entry', label: '今日任务' },
  { routeName: 'mobile-report-history', label: '历史' },
  { routeName: 'entry-drafts', label: '草稿' }
]

function go(routeName) {
  if (route.name === routeName) return
  router.push({ name: routeName })
}
</script>

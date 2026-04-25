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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { buildShellNavigation } from '../config/navigation'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = computed(() => buildShellNavigation('entry', auth).flatMap((group) => group.items))

function go(routeName) {
  if (route.name === routeName) return
  router.push({ name: routeName })
}
</script>

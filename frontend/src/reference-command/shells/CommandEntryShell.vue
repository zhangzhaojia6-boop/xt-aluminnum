<template>
  <div class="cmd-page cmd-shell cmd-shell--entry" data-testid="entry-shell">
    <aside class="cmd-shell__side app-shell__aside">
      <div class="cmd-shell__brand" v-html="commandLogoHtml('独立填报端')" />
      <nav class="cmd-shell__nav" aria-label="录入端导航">
        <RouterLink class="el-menu-item" :to="{ name: 'mobile-entry' }">今日填报</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'dynamic-entry-form' }">填报流程</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'mobile-report-history' }">历史记录</RouterLink>
      </nav>
    </aside>
    <main class="cmd-shell__main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { commandLogoHtml } from '../assets/logo.js'
</script>

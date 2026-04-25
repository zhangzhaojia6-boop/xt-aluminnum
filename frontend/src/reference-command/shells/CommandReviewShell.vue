<template>
  <div class="cmd-page cmd-shell cmd-shell--review" data-testid="review-shell">
    <aside class="cmd-shell__side app-shell__aside">
      <div class="cmd-shell__brand">
        <span data-testid="review-brand-mark" v-html="commandLogoMark" />
        <strong data-testid="review-brand-title">鑫泰铝业生产协同系统</strong>
      </div>
      <nav class="cmd-shell__nav" aria-label="审阅端导航">
        <div class="app-nav-group__title">总览中心</div>
        <RouterLink class="el-menu-item" :to="{ name: 'review-overview-home' }">系统总览</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'factory-dashboard' }">工厂看板</RouterLink>
        <div class="app-nav-group__title">审阅处置</div>
        <RouterLink class="el-menu-item" :to="{ name: 'review-task-center' }">审阅中心</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'review-report-center' }">日报交付</RouterLink>
        <div class="app-nav-group__title">经营与智能</div>
        <RouterLink class="el-menu-item" :to="{ name: 'review-cost-accounting' }">成本效益</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'review-brain-center' }">AI 总大脑</RouterLink>
      </nav>
    </aside>
    <main class="cmd-shell__main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { commandLogoMark } from '../assets/logo.js'
</script>

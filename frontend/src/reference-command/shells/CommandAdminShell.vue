<template>
  <div class="cmd-page cmd-shell cmd-shell--admin" data-testid="admin-shell">
    <aside class="cmd-shell__side app-shell__aside">
      <div class="cmd-shell__brand" v-html="commandLogoHtml('管理控制台')" />
      <div class="cmd-shell__switch">
        <button type="button" class="cmd-button" @click="$router.push('/entry')">录入端</button>
        <button type="button" class="cmd-button" @click="$router.push('/review/overview')">审阅端</button>
      </div>
      <nav class="cmd-shell__nav" aria-label="管理端导航">
        <RouterLink class="el-menu-item" :to="{ name: 'ingestion-center' }">数据接入与字段映射中心</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'ops-reliability' }">系统运维</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'governance-center' }">权限治理</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'master-workshop' }">主数据</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'workshop-template-config' }">模板中心</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'admin-users' }">用户管理</RouterLink>
        <RouterLink class="el-menu-item" :to="{ name: 'admin-roadmap-center' }">路线图</RouterLink>
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

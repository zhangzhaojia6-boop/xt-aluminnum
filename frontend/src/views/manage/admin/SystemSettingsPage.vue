<template>
  <section class="xt-system-settings" data-testid="system-settings-page">
    <header class="xt-system-settings__header">
      <span>系统配置</span>
      <h1>系统设置</h1>
    </header>

    <nav class="xt-system-settings__grid" aria-label="系统设置入口">
      <RouterLink
        v-for="item in settingLinks"
        :key="item.path"
        class="xt-system-settings__card"
        :to="item.path"
      >
        <span>{{ item.title }}</span>
      </RouterLink>
    </nav>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'

const settingLinks = [
  { title: '主数据', path: '/manage/master' },
  { title: '别名映射', path: '/manage/alias' },
  { title: '用户管理', path: '/manage/admin/users' },
  { title: '模板中心', path: '/manage/admin/templates' },
  { title: '规则配置', path: '/manage/admin/rules' },
  { title: '权限治理', path: '/manage/admin/governance' },
  { title: 'QR 打印', path: '/manage/admin/qr-print' },
  { title: 'AI 助手', path: '/manage/ai-assistant' },
]
</script>

<style scoped>
.xt-system-settings {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-4);
}

.xt-system-settings__header {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-1);
}

.xt-system-settings__header span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 800;
}

.xt-system-settings__header h1 {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-2xl);
  font-weight: 850;
  letter-spacing: -0.02em;
}

.xt-system-settings__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--xt-space-3);
}

.xt-system-settings__card {
  display: flex;
  align-items: center;
  min-height: 76px;
  padding: var(--xt-space-4);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font-size: var(--xt-text-base);
  font-weight: 850;
  text-decoration: none;
  transition: border-color var(--xt-motion-fast) var(--xt-ease), transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-system-settings__card:hover {
  border-color: var(--xt-border-strong);
  transform: translateY(-1px);
}
</style>

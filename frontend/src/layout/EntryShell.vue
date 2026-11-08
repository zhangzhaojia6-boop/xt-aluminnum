<template>
  <div class="xt-entry" data-testid="entry-shell">
    <header class="xt-entry__topbar">
      <RouterLink class="xt-entry__brand" to="/entry" aria-label="鑫泰铝业数据中枢填报端">
        <XtLogo variant="icon" />
        <span>现场填报</span>
      </RouterLink>
      <div class="xt-entry__shift">{{ currentShift }}</div>
      <span class="xt-entry__user">{{ userName }}</span>
    </header>

    <main class="xt-entry__content">
      <RouterView v-slot="{ Component }">
        <Transition name="xt-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

    <nav class="xt-entry__tabbar" aria-label="录入端导航">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="xt-entry__tab"
        :class="{ 'is-active': isActive(tab.path) }"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <span>{{ tab.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { Document, EditPen, HomeFilled, Tickets } from '@element-plus/icons-vue'

import { XtLogo } from '../components/xt'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth = useAuthStore()

const userName = computed(() => auth.displayName || auth.user?.name || auth.user?.username || '操作员')
const currentShift = computed(() => auth.machineContext?.machine_name || auth.machineContext?.machine_code || '当前班次')

const tabs = [
  { path: '/entry', label: '首页', icon: HomeFilled },
  { path: '/entry/fill', label: '录入', icon: EditPen },
  { path: '/entry/history', label: '历史', icon: Tickets },
  { path: '/entry/drafts', label: '草稿', icon: Document },
]

function isActive(path) {
  if (path === '/entry') return route.path === '/entry'
  return route.path.startsWith(path)
}
</script>

<style scoped>
.xt-entry {
  --xt-tabbar-height: 64px;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 600px;
  margin: 0 auto;
  background: var(--xt-bg-page);
  color: var(--xt-text);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.xt-entry__topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: calc(8px + env(safe-area-inset-top)) 20px 8px;
  border-bottom: 1px solid var(--xt-border);
  background: var(--xt-bg-page);
}

.xt-entry__brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--xt-text);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}

.xt-entry__brand :deep(.xt-logo__icon) {
  width: 28px;
  height: 28px;
}

.xt-entry__shift {
  max-width: 34%;
  min-width: 0;
  overflow: hidden;
  color: var(--xt-primary);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-entry__user {
  min-width: 0;
  margin-left: auto;
  overflow: hidden;
  color: var(--xt-text-muted);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-entry__content {
  flex: 1;
  min-width: 0;
  padding-bottom: calc(var(--xt-tabbar-height) + env(safe-area-inset-bottom));
}

.xt-entry__tabbar {
  position: fixed;
  bottom: 0;
  left: 50%;
  z-index: 30;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  width: min(100%, 600px);
  min-height: var(--xt-tabbar-height);
  padding-bottom: env(safe-area-inset-bottom);
  border-top: 1px solid var(--xt-border);
  background: var(--xt-bg-page);
  transform: translateX(-50%);
}

.xt-entry__tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 56px;
  color: var(--xt-text-muted);
  font-size: 12px;
  text-decoration: none;
  touch-action: manipulation;
  transition: color 150ms ease;
}

.xt-entry__tab .el-icon {
  font-size: 22px;
}

.xt-entry__tab.is-active {
  color: var(--xt-primary);
  font-weight: 600;
}

.xt-entry :deep(.mobile-shell) {
  background: transparent;
}

.xt-entry :deep(.panel),
.xt-entry :deep(.mobile-top),
.xt-entry :deep(.mobile-card.el-card),
.xt-entry :deep(.mobile-placeholder),
.xt-entry :deep(.mobile-inline-state),
.xt-entry :deep(.template-empty),
.xt-entry :deep(.mobile-ocr-field),
.xt-entry :deep(.mobile-upload-box) {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  color: var(--xt-text);
}

.xt-entry :deep(.mobile-history-item),
.xt-entry :deep(.mobile-attendance-card),
.xt-entry :deep(.mobile-overview-item),
.xt-entry :deep(.mobile-history-grid > div) {
  border: 0;
  border-bottom: 1px solid var(--xt-border);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.xt-entry :deep(.mobile-sticky-actions) {
  border: 0;
  border-top: 1px solid var(--xt-border);
  border-radius: 0;
  background: var(--xt-bg-page);
  box-shadow: none;
}

.xt-entry :deep(.mobile-attendance-card.is-anomaly) {
  border-bottom-color: var(--xt-warning);
}

.xt-entry :deep(.mobile-top h1),
.xt-entry :deep(.page-title h1),
.xt-entry :deep(.panel-header h1) {
  color: var(--xt-text);
  font-size: 28px;
  font-weight: 600;
  text-shadow: none;
}

.xt-entry :deep(.mobile-top p),
.xt-entry :deep(.page-title p),
.xt-entry :deep(.note),
.xt-entry :deep(.mobile-history-meta),
.xt-entry :deep(.mobile-history-note),
.xt-entry :deep(.mobile-field-meta),
.xt-entry :deep(.mobile-attendance-card__clock),
.xt-entry :deep(.mobile-attendance-card__metrics),
.xt-entry :deep(.consumable-actions__hint),
.xt-entry :deep(.consumable-fields__type),
.xt-entry :deep(.el-form-item__label),
.xt-entry :deep(.panel-subtitle),
.xt-entry :deep(.consumable-fields__hint) {
  color: var(--xt-text-secondary);
}

.xt-entry :deep(.mobile-history-title),
.xt-entry :deep(.mobile-attendance-card__name),
.xt-entry :deep(.mobile-overview-item strong),
.xt-entry :deep(.mobile-history-grid strong),
.xt-entry :deep(.mobile-field label) {
  color: var(--xt-text);
}

.xt-entry :deep(.el-card) {
  border: 0;
  background: transparent;
  box-shadow: none;
  color: var(--xt-text);
}

.xt-entry :deep(.el-card__header) {
  padding-inline: 0;
  border-bottom: 1px solid var(--xt-border);
  color: var(--xt-text);
  font-weight: 600;
}

.xt-entry :deep(.el-card__body) {
  padding-inline: 0;
}

.xt-entry :deep(.el-input__wrapper),
.xt-entry :deep(.el-select__wrapper),
.xt-entry :deep(.el-textarea__inner),
.xt-entry :deep(.el-input-number .el-input__wrapper),
.xt-entry :deep(.mobile-history-date .el-input__wrapper) {
  min-height: 48px;
  border-radius: 4px;
  background: var(--xt-bg-page);
  box-shadow: 0 0 0 1px var(--xt-border) inset;
}

.xt-entry :deep(.el-input__inner),
.xt-entry :deep(.el-select__placeholder),
.xt-entry :deep(.el-select__selected-item),
.xt-entry :deep(.el-textarea__inner) {
  color: var(--xt-text);
  font-size: 16px;
}

.xt-entry :deep(.el-button) {
  min-height: 48px;
  border-radius: 4px;
  box-shadow: none;
  font-size: 16px;
  touch-action: manipulation;
}

.xt-entry :deep(.el-button--primary) {
  border-color: var(--xt-primary);
  background: var(--xt-primary);
  color: #fff;
}

.xt-entry :deep(.el-button.is-plain) {
  border-color: var(--xt-border);
  background: var(--xt-bg-page);
  color: var(--xt-text);
}

.xt-entry :deep(.el-button--primary.is-plain) {
  border-color: var(--xt-primary);
  color: var(--xt-primary);
}

.xt-entry :deep(.el-button--danger.is-plain) {
  border-color: var(--xt-danger);
  color: var(--xt-danger);
}

.xt-entry :deep(.el-alert) {
  border-radius: 4px;
}

@media (min-width: 900px) {
  .xt-entry {
    max-width: 980px;
  }

  .xt-entry__tabbar {
    width: min(100%, 980px);
  }
}

.xt-fade-enter-active,
.xt-fade-leave-active {
  transition: opacity 150ms ease;
}

.xt-fade-enter-from,
.xt-fade-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .xt-fade-enter-active,
  .xt-fade-leave-active,
  .xt-entry__tab {
    transition: none;
  }
}
</style>

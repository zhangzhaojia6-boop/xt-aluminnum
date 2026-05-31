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
  --entry-canvas: #050c17;
  --entry-canvas-deep: #020812;
  --entry-panel: rgba(8, 24, 45, 0.78);
  --entry-panel-strong: rgba(12, 34, 62, 0.9);
  --entry-line: rgba(0, 242, 255, 0.16);
  --entry-line-strong: rgba(0, 242, 255, 0.34);
  --entry-cyan: #00f2ff;
  --entry-cyan-soft: rgba(0, 242, 255, 0.12);
  --entry-amber: #ffab00;
  --entry-danger: #ff5c35;
  --xt-bg-page: transparent;
  --xt-bg-shell: var(--entry-canvas);
  --xt-bg-panel: var(--entry-panel);
  --xt-bg-panel-soft: rgba(11, 31, 56, 0.78);
  --xt-bg-panel-muted: rgba(17, 45, 77, 0.72);
  --xt-bg-panel-strong: var(--entry-panel-strong);
  --xt-bg-depth: var(--entry-canvas-deep);
  --xt-bg-ink: #06101f;
  --xt-bg-ink-soft: #0a1a2e;
  --xt-bg-ink-panel: #0e2540;
  --xt-primary: var(--entry-cyan);
  --xt-primary-hover: #74f5ff;
  --xt-primary-active: #00b7c3;
  --xt-primary-light: var(--entry-cyan-soft);
  --xt-primary-soft: rgba(0, 242, 255, 0.08);
  --xt-primary-border: var(--entry-line-strong);
  --xt-text: rgba(236, 248, 255, 0.95);
  --xt-text-secondary: rgba(185, 218, 235, 0.74);
  --xt-text-muted: rgba(156, 190, 212, 0.62);
  --xt-text-soft: rgba(208, 230, 242, 0.86);
  --xt-border: var(--entry-line);
  --xt-border-light: rgba(0, 242, 255, 0.1);
  --xt-border-strong: var(--entry-line-strong);
  --app-bg: transparent;
  --app-panel: var(--entry-panel);
  --app-panel-soft: rgba(11, 31, 56, 0.78);
  --app-text: var(--xt-text);
  --app-muted: var(--xt-text-secondary);
  --app-border: var(--entry-line);
  --app-focus-ring: 0 0 0 3px rgba(0, 242, 255, 0.18);
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 600px;
  margin: 0 auto;
  background:
    radial-gradient(circle at 18% 0%, rgba(0, 242, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 18%, rgba(0, 119, 255, 0.12), transparent 38%),
    linear-gradient(180deg, var(--entry-canvas) 0%, var(--entry-canvas-deep) 100%);
  color: var(--xt-text);
  border-right: 1px solid var(--entry-line);
  border-left: 1px solid var(--entry-line);
  box-shadow: 0 0 48px rgba(0, 242, 255, 0.08);
  overflow: hidden;
}

.xt-entry::before {
  content: '';
  position: fixed;
  inset: 0 auto 0 50%;
  z-index: 0;
  width: min(100%, 600px);
  pointer-events: none;
  background:
    linear-gradient(rgba(0, 242, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.04) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.75), transparent 78%);
  opacity: 0.5;
  transform: translateX(-50%);
}

.xt-entry::after {
  content: '';
  position: fixed;
  left: 50%;
  top: 0;
  z-index: 0;
  width: min(100%, 600px);
  height: 160px;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(0, 242, 255, 0.16), transparent);
  opacity: 0.42;
  transform: translateX(-50%);
}

.xt-entry__topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  min-height: 56px;
  padding: calc(var(--xt-space-2) + env(safe-area-inset-top)) var(--xt-space-4) var(--xt-space-2);
  background: linear-gradient(180deg, rgba(5, 15, 28, 0.92), rgba(5, 13, 24, 0.78));
  border-bottom: 1px solid var(--entry-line);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 14px 34px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
}

.xt-entry__brand {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  text-decoration: none;
}

.xt-entry__brand span {
  letter-spacing: 0.04em;
  text-shadow: 0 0 18px rgba(0, 242, 255, 0.2);
}

.xt-entry__shift {
  max-width: 34%;
  min-width: 0;
  padding: 3px var(--xt-space-2);
  border: 1px solid rgba(0, 242, 255, 0.22);
  border-radius: var(--xt-radius-lg);
  background: rgba(0, 242, 255, 0.08);
  color: rgba(216, 249, 255, 0.9);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-entry__user {
  max-width: 28%;
  min-width: 0;
  margin-left: auto;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-entry__content {
  position: relative;
  z-index: 1;
  flex: 1;
  padding: var(--xt-space-4);
  padding-bottom: calc(var(--xt-tabbar-height) + var(--xt-space-5) + env(safe-area-inset-bottom));
}

.xt-entry__tabbar {
  position: fixed;
  bottom: 0;
  left: 50%;
  z-index: 100;
  width: min(100%, 600px);
  min-height: calc(var(--xt-tabbar-height) + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: var(--xt-space-1);
  padding: var(--xt-space-1) var(--xt-space-2) calc(var(--xt-space-1) + env(safe-area-inset-bottom));
  background: linear-gradient(180deg, rgba(9, 24, 43, 0.72), rgba(3, 10, 20, 0.94));
  border-top: 1px solid var(--entry-line);
  box-shadow: 0 -18px 40px rgba(0, 0, 0, 0.32), 0 -1px 0 rgba(255, 255, 255, 0.05) inset;
  backdrop-filter: blur(18px);
  transform: translateX(-50%);
}

.xt-entry__tabbar::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 0;
  width: 42%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.9), transparent);
  animation: xtEntryScan 4.8s linear infinite;
}

.xt-entry__tab {
  min-width: 64px;
  min-height: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  justify-content: center;
  padding: var(--xt-space-1) var(--xt-space-3);
  border: 1px solid transparent;
  border-radius: var(--xt-radius-lg);
  color: var(--xt-text-muted);
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-entry__tab .el-icon {
  font-size: 20px;
}

.xt-entry__tab.is-active {
  border-color: rgba(0, 242, 255, 0.26);
  background: linear-gradient(180deg, rgba(0, 242, 255, 0.18), rgba(0, 242, 255, 0.08));
  color: #e6fdff;
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.xt-entry__tab:active {
  transform: scale(0.96);
}

@media (hover: hover) {
  .xt-entry__tab:hover {
    border-color: rgba(0, 242, 255, 0.2);
    background: rgba(0, 242, 255, 0.08);
    color: var(--xt-text);
  }
}

.xt-entry :deep(.mobile-shell) {
  background: transparent;
  color: var(--xt-text);
}

.xt-entry :deep(.panel),
.xt-entry :deep(.mobile-top),
.xt-entry :deep(.mobile-card.el-card),
.xt-entry :deep(.mobile-placeholder),
.xt-entry :deep(.mobile-inline-state),
.xt-entry :deep(.template-empty) {
  border: 1px solid var(--entry-line);
  background:
    linear-gradient(145deg, rgba(12, 34, 62, 0.84), rgba(5, 14, 28, 0.74)),
    radial-gradient(circle at 12% 0%, rgba(0, 242, 255, 0.1), transparent 42%);
  color: var(--xt-text);
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(14px);
}

.xt-entry :deep(.mobile-top h1),
.xt-entry :deep(.page-title h1) {
  color: var(--xt-text);
  text-shadow: 0 0 20px rgba(0, 242, 255, 0.16);
}

.xt-entry :deep(.mobile-top p),
.xt-entry :deep(.page-title p),
.xt-entry :deep(.note) {
  color: var(--xt-text-secondary);
}

.xt-entry :deep(.el-card) {
  --el-card-bg-color: transparent;
  --el-card-border-color: var(--entry-line);
  color: var(--xt-text);
}

.xt-entry :deep(.el-card__header) {
  border-bottom-color: var(--entry-line);
  color: var(--xt-text);
}

.xt-entry :deep(.el-input__wrapper),
.xt-entry :deep(.el-select__wrapper),
.xt-entry :deep(.el-textarea__inner) {
  background: rgba(3, 12, 24, 0.72);
  border: 1px solid rgba(0, 242, 255, 0.16);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);
}

.xt-entry :deep(.el-input__inner),
.xt-entry :deep(.el-select__placeholder),
.xt-entry :deep(.el-textarea__inner) {
  color: var(--xt-text);
}

.xt-entry :deep(.el-button--primary) {
  border-color: rgba(0, 242, 255, 0.72);
  background: linear-gradient(135deg, #00f2ff, #74f5ff);
  color: #001d22;
  box-shadow: 0 0 28px rgba(0, 242, 255, 0.22);
}

.xt-entry :deep(.el-button.is-plain) {
  border-color: rgba(0, 242, 255, 0.24);
  background: rgba(0, 242, 255, 0.08);
  color: var(--xt-text);
}

@keyframes xtEntryScan {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(240%); }
}

@media (max-width: 600px) {
  .xt-entry {
    border-right: 0;
    border-left: 0;
  }
}
</style>

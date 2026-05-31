<template>
  <section class="xt-system-settings" data-testid="system-settings-page">
    <div class="xt-system-settings__backdrop" aria-hidden="true"></div>

    <div class="xt-system-settings__layout">
      <div class="xt-system-settings__main">
        <header class="xt-system-settings__header">
          <div>
            <span>系统配置</span>
            <h1>系统设置</h1>
          </div>
          <strong>ENV: PRODUCTION_XT</strong>
        </header>

        <nav class="xt-system-settings__groups" aria-label="系统设置入口">
          <section
            v-for="group in settingGroups"
            :key="group.label"
            class="xt-system-settings__group"
          >
            <div class="xt-system-settings__group-label">[ {{ group.label }} ]</div>
            <div class="xt-system-settings__grid">
              <RouterLink
                v-for="item in group.items"
                :key="item.path"
                class="xt-system-settings__card"
                :class="`is-${item.tone}`"
                :to="item.path"
              >
                <span class="xt-system-settings__scan" aria-hidden="true"></span>
                <span class="xt-system-settings__icon">
                  <el-icon><component :is="item.icon" /></el-icon>
                </span>
                <span class="xt-system-settings__copy">
                  <span>{{ item.title }}</span>
                  <small>{{ item.tag }}</small>
                </span>
              </RouterLink>
            </div>
          </section>
        </nav>
      </div>

      <aside class="xt-system-settings__side" aria-label="系统状态">
        <section class="xt-system-settings__gauge">
          <span>配置完整度</span>
          <div class="xt-system-settings__ring" aria-hidden="true">
            <b>92.5%</b>
            <small>系统优秀</small>
          </div>
        </section>

        <section class="xt-system-settings__status">
          <h2>中枢状态</h2>
          <div v-for="item in statusItems" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </section>
      </aside>
    </div>

    <footer class="xt-system-settings__linkage" aria-label="系统联动监控">
      <strong>系统联动监控</strong>
      <span v-for="item in linkageItems" :key="item">{{ item }}</span>
    </footer>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import {
  ChatDotRound,
  Connection,
  Files,
  Lock,
  Printer,
  Setting,
  Tickets,
  User
} from '@element-plus/icons-vue'

const settingGroups = [
  {
    label: '配置',
    items: [
      { title: '主数据', path: '/manage/master', tag: '已就绪', icon: Files, tone: 'ready' },
      { title: '别名映射', path: '/manage/alias', tag: '实时同步', icon: Connection, tone: 'ready' },
      { title: '规则配置', path: '/manage/admin/rules', tag: '规则引擎', icon: Setting, tone: 'warning' },
      { title: '模板中心', path: '/manage/admin/templates', tag: '工业报表', icon: Tickets, tone: 'neutral' }
    ]
  },
  {
    label: '权限',
    items: [
      { title: '用户管理', path: '/manage/admin/users', tag: '组织架构', icon: User, tone: 'neutral' },
      { title: '权限治理', path: '/manage/admin/governance', tag: '安全中心', icon: Lock, tone: 'neutral' }
    ]
  },
  {
    label: '工具 / 助手',
    items: [
      { title: 'QR 打印', path: '/manage/admin/qr-print', tag: '标签服务', icon: Printer, tone: 'neutral' },
      { title: 'AI 助手', path: '/manage/ai-assistant', tag: '智能决策', icon: ChatDotRound, tone: 'ready' }
    ]
  }
]

const settingLinks = settingGroups.flatMap((group) => group.items)
const statusItems = [
  { label: '核心模块', value: `${settingLinks.length}/8` },
  { label: '配置通道', value: 'ACTIVE' },
  { label: '入口状态', value: 'ONLINE' }
]
const linkageItems = ['MASTER_DATA', 'ALIAS_SYNC', 'RULE_ENGINE', 'USER_RBAC', 'QR_SERVICE', 'AI_ASSIST']
</script>

<style scoped>
.xt-system-settings {
  position: relative;
  isolation: isolate;
  display: grid;
  gap: var(--xt-space-4);
  min-height: calc(100vh - var(--xt-topbar-height) - var(--xt-space-10));
  overflow-x: hidden;
  color: rgba(225, 253, 255, 0.94);
}

.xt-system-settings__backdrop {
  position: absolute;
  inset: -24px 0;
  z-index: -1;
  opacity: 0.72;
  background:
    linear-gradient(rgba(0, 242, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.04) 1px, transparent 1px),
    radial-gradient(circle at 78% 12%, rgba(0, 242, 255, 0.16), transparent 28%);
  background-size: 36px 36px, 36px 36px, 100% 100%;
  pointer-events: none;
}

.xt-system-settings__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: var(--xt-space-4);
}

.xt-system-settings__main,
.xt-system-settings__side,
.xt-system-settings__linkage,
.xt-system-settings__header,
.xt-system-settings__card,
.xt-system-settings__status,
.xt-system-settings__gauge {
  border: 1px solid rgba(0, 242, 255, 0.16);
  background:
    linear-gradient(180deg, rgba(18, 44, 70, 0.54), rgba(4, 14, 26, 0.72)),
    rgba(4, 18, 32, 0.66);
  box-shadow:
    inset 1px 1px 0 rgba(255, 255, 255, 0.05),
    0 22px 56px rgba(0, 12, 28, 0.24);
  backdrop-filter: blur(12px);
}

.xt-system-settings__main {
  display: grid;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4);
  overflow: hidden;
  border-radius: 14px;
}

.xt-system-settings__header {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-3);
  min-height: 108px;
  padding: var(--xt-space-4);
  overflow: hidden;
  border-left: 4px solid rgba(0, 242, 255, 0.86);
  border-radius: 12px;
}

.xt-system-settings__header::after,
.xt-system-settings__linkage::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent, rgba(0, 242, 255, 0.1), transparent);
  transform: translateY(-100%);
  animation: xtSettingsScan 7s linear infinite;
  content: "";
  pointer-events: none;
}

.xt-system-settings__header span {
  color: rgba(116, 245, 255, 0.86);
  font-size: var(--xt-text-sm);
  font-weight: 800;
  letter-spacing: 0.08em;
}

.xt-system-settings__header h1 {
  margin: 0;
  color: rgba(225, 253, 255, 0.98);
  font-family: var(--xt-font-display);
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 900;
  letter-spacing: -0.02em;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.18);
}

.xt-system-settings__header strong {
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid rgba(0, 242, 255, 0.3);
  border-radius: 8px;
  background: rgba(0, 242, 255, 0.09);
  color: rgba(116, 245, 255, 0.92);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  letter-spacing: 0.06em;
}

.xt-system-settings__groups {
  display: grid;
  gap: var(--xt-space-4);
}

.xt-system-settings__group {
  display: grid;
  gap: var(--xt-space-2);
}

.xt-system-settings__group-label {
  padding-left: var(--xt-space-2);
  border-left: 1px solid rgba(0, 242, 255, 0.42);
  color: rgba(204, 220, 249, 0.76);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  letter-spacing: 0.12em;
}

.xt-system-settings__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-system-settings__card {
  position: relative;
  min-height: 126px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  overflow: hidden;
  border-radius: 12px;
  color: rgba(225, 253, 255, 0.92);
  text-decoration: none;
  transition:
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-system-settings__scan {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent, rgba(0, 242, 255, 0.13), transparent);
  transform: translateY(-110%);
  transition: transform 560ms var(--xt-ease);
  pointer-events: none;
}

.xt-system-settings__icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 242, 255, 0.22);
  border-radius: 10px;
  background: rgba(8, 31, 52, 0.7);
  color: rgba(116, 245, 255, 0.92);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);
  transition: box-shadow var(--xt-motion-fast) var(--xt-ease);
}

.xt-system-settings__copy {
  display: grid;
  gap: var(--xt-space-2);
}

.xt-system-settings__copy > span {
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.xt-system-settings__copy small {
  width: fit-content;
  padding: 3px var(--xt-space-2);
  border: 1px solid rgba(132, 148, 149, 0.28);
  border-radius: 6px;
  background: rgba(49, 53, 60, 0.34);
  color: rgba(185, 202, 203, 0.78);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-system-settings__card.is-ready .xt-system-settings__copy small {
  border-color: rgba(0, 242, 255, 0.26);
  background: rgba(0, 242, 255, 0.1);
  color: rgba(116, 245, 255, 0.9);
}

.xt-system-settings__card.is-warning .xt-system-settings__copy small {
  border-color: rgba(255, 171, 0, 0.32);
  background: rgba(255, 171, 0, 0.11);
  color: rgba(255, 214, 128, 0.92);
}

@media (hover: hover) {
  .xt-system-settings__card:hover {
    border-color: rgba(0, 242, 255, 0.46);
    color: rgba(225, 253, 255, 1);
    box-shadow:
      inset 1px 1px 0 rgba(255, 255, 255, 0.06),
      0 0 28px rgba(0, 242, 255, 0.13);
    transform: translateY(-2px);
  }

  .xt-system-settings__card:hover .xt-system-settings__scan {
    transform: translateY(110%);
  }

  .xt-system-settings__card:hover .xt-system-settings__icon {
    box-shadow: 0 0 20px rgba(0, 242, 255, 0.26);
  }
}

.xt-system-settings__side {
  display: grid;
  align-content: start;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4);
  border-radius: 14px;
}

.xt-system-settings__gauge,
.xt-system-settings__status {
  border-radius: 12px;
  padding: var(--xt-space-4);
}

.xt-system-settings__gauge {
  display: grid;
  place-items: center;
  gap: var(--xt-space-4);
}

.xt-system-settings__gauge > span,
.xt-system-settings__status h2 {
  width: 100%;
  margin: 0;
  color: rgba(225, 253, 255, 0.9);
  font-size: var(--xt-text-base);
  font-weight: 900;
}

.xt-system-settings__ring {
  width: 168px;
  height: 168px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: var(--xt-space-1);
  border-radius: 50%;
  background:
    radial-gradient(circle, rgba(4, 14, 26, 0.92) 54%, transparent 56%),
    conic-gradient(rgba(0, 242, 255, 0.98) 0 333deg, rgba(0, 242, 255, 0.11) 333deg 360deg);
  box-shadow:
    0 0 24px rgba(0, 242, 255, 0.18),
    inset 0 0 24px rgba(0, 242, 255, 0.08);
}

.xt-system-settings__ring b {
  color: rgba(116, 245, 255, 0.98);
  font-family: var(--xt-font-display);
  font-size: 34px;
  line-height: 1;
}

.xt-system-settings__ring small {
  color: rgba(0, 242, 255, 0.76);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-system-settings__status {
  display: grid;
  gap: var(--xt-space-3);
}

.xt-system-settings__status div {
  display: flex;
  justify-content: space-between;
  gap: var(--xt-space-3);
  color: rgba(185, 202, 203, 0.75);
  font-size: var(--xt-text-sm);
}

.xt-system-settings__status strong {
  color: rgba(116, 245, 255, 0.92);
  font-family: var(--xt-font-mono);
}

.xt-system-settings__linkage {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--xt-space-4);
  min-height: 58px;
  padding: 0 var(--xt-space-4);
  overflow: hidden;
  border-radius: 14px;
}

.xt-system-settings__linkage strong {
  padding-right: var(--xt-space-4);
  border-right: 1px solid rgba(0, 242, 255, 0.2);
  color: rgba(116, 245, 255, 0.94);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.xt-system-settings__linkage span {
  position: relative;
  color: rgba(185, 202, 203, 0.72);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  letter-spacing: 0.06em;
}

.xt-system-settings__linkage span::before {
  width: 7px;
  height: 7px;
  display: inline-block;
  margin-right: var(--xt-space-2);
  border-radius: 50%;
  background: rgba(0, 242, 255, 0.92);
  box-shadow: 0 0 10px rgba(0, 242, 255, 0.62);
  content: "";
}

@keyframes xtSettingsScan {
  0% { transform: translateY(-100%); opacity: 0; }
  28% { opacity: 0.74; }
  100% { transform: translateY(100%); opacity: 0; }
}

@media (max-width: 1180px) {
  .xt-system-settings__layout {
    grid-template-columns: 1fr;
  }

  .xt-system-settings__side {
    grid-template-columns: minmax(240px, 320px) 1fr;
  }
}

@media (max-width: 720px) {
  .xt-system-settings {
    min-height: 0;
  }

  .xt-system-settings__main,
  .xt-system-settings__side {
    padding: var(--xt-space-3);
  }

  .xt-system-settings__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .xt-system-settings__grid,
  .xt-system-settings__side {
    grid-template-columns: 1fr;
  }

  .xt-system-settings__linkage {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--xt-space-4);
  }

  .xt-system-settings__linkage strong {
    border-right: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-system-settings__header::after,
  .xt-system-settings__linkage::after {
    animation: none;
  }

  .xt-system-settings__card,
  .xt-system-settings__scan,
  .xt-system-settings__icon {
    transition: none;
  }
}
</style>

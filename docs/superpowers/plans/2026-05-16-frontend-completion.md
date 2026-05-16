# 数据中枢 前端完全体方案

**Date:** 2026-05-16
**Executor:** Claude Opus（前端设计 + 实现）
**Base:** `D:\zzj Claude code\aluminum-bypass\frontend`
**Branch:** `codex/gai`

## 当前状态

- 65+ Vue 页面，41 组件，4 stores，21 API 模块
- 设计系统完整：xt-tokens / xt-base / xt-motion / xt-hud / industrial.css
- 构建 2.13s，221 测试全绿
- echarts 独立 chunk + 异步主题注册
- IndexedDB 重试队列（useRetryQueue）已有
- 无 Service Worker，无 PWA manifest
- E2E spec 33 个但无 Playwright 配置（不可执行）
- 无前端错误监控

## 约束

- 不引入新依赖（除 vite-plugin-pwa、@playwright/test）
- 不改后端 API 契约
- 匹配现有设计系统风格
- 每个任务独立可提交

---

## F1. Service Worker + PWA 离线体验

**目标：** 移动端填报断网可用，恢复后自动同步

**交付物：**
- `vite.config.js` 添加 `vite-plugin-pwa` 配置
- `public/manifest.json`（图标、主题色、display: standalone）
- `src/sw-register.js`（SW 注册 + 更新提示）
- `public/offline.html`（离线 fallback 页面）
- 修改 `useRetryQueue.js` 监听 SW 的 sync 事件

**缓存策略：**
```
App Shell (index.html, CSS, JS) → CacheFirst
API 请求 → NetworkFirst, fallback to cache
静态资源 (fonts, icons) → CacheFirst
图片 → StaleWhileRevalidate
```

**验收：**
1. `npm run build` 生成 sw.js
2. 断网状态下 /mobile/shift-report 可打开并填写
3. 恢复网络后队列自动提交
4. Chrome DevTools > Application > Service Workers 显示 active

---

## F2. 前端错误监控 + 性能埋点

**目标：** 生产异常可追溯，性能可度量

**交付物：**
- `src/plugins/errorMonitor.js`
- `src/composables/usePerformance.js`
- `src/api/telemetry.js`

**实现：**
```javascript
// src/plugins/errorMonitor.js
export function installErrorMonitor(app) {
  app.config.errorHandler = (err, instance, info) => {
    reportError({ message: err.message, stack: err.stack, info, url: location.href })
  }
  window.addEventListener('unhandledrejection', (e) => {
    reportError({ message: e.reason?.message, stack: e.reason?.stack, url: location.href })
  })
}

// src/composables/usePerformance.js
export function usePerformance(routeName) {
  onMounted(() => {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        reportPerf({ route: routeName, metric: entry.name, value: entry.startTime })
      }
    })
    observer.observe({ type: 'largest-contentful-paint', buffered: true })
  })
}
```

**验收：**
1. 故意抛错 → 控制台无未捕获异常 + 上报请求发出
2. 路由切换 → performance 数据采集
3. 后端 telemetry 端点收到数据（需 B6 配合）

---

## F3. E2E 测试可执行化

**目标：** `npx playwright test` 在 CI 中可运行

**交付物：**
- `playwright.config.ts`
- `e2e/fixtures/auth.ts`（登录态注入）
- 修改现有 33 个 spec 为 Playwright 语法（或新建 10 个核心 spec）

**配置：**
```typescript
// playwright.config.ts
export default defineConfig({
  testDir: './e2e',
  baseURL: 'http://localhost:5173',
  use: { headless: true, screenshot: 'only-on-failure' },
  webServer: { command: 'npm run dev', port: 5173, reuseExistingServer: true },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
  ],
})
```

**核心覆盖（优先级）：**
1. 登录流程（用户名密码 → 跳转管理端）
2. 管理端导航（侧边栏展开/折叠 → 路由切换）
3. 移动端填报（打开表单 → 填写 → 提交）
4. 实时看板（数据加载 → 图表渲染）
5. 审批流（查看待审 → 通过/退回）

**验收：**
1. `npx playwright test --project=chromium` ≥ 10 个 pass
2. `npx playwright test --project=mobile` ≥ 5 个 pass

---

## F4. 移动端体验精修

**目标：** 车间工人高效使用

**交付物：**
- `src/composables/usePullRefresh.js`
- `src/components/xt/XtSkeleton.vue`
- `src/components/xt/XtCameraGuide.vue`
- 修改 MobileEntry.vue / ShiftReportForm.vue / CoilEntryWorkbench.vue

**细节：**
| 改进点 | 实现 |
|--------|------|
| 下拉刷新 | touch 手势 + 旋转动画 + 触发 API reload |
| 骨架屏 | 加载态 ≤ 300ms 显示，匹配页面布局 |
| 大触控区 | 所有可点击元素 min-height: 44px |
| 弱网提示 | navigator.connection 监听 + 顶部 banner |
| 摄像头引导 | 首次扫码前检测权限 + 友好提示 |

**验收：**
1. 移动端 Chrome DevTools 模拟 3G → 骨架屏出现
2. 下拉手势触发刷新动画
3. 所有按钮触控区 ≥ 44×44px

---

## F5. 可访问性基线

**目标：** WCAG 2.1 AA 基线

**交付物：**
- `src/composables/useFocusTrap.js`
- 修改所有 modal/dialog 组件添加 focus trap
- 图表组件添加 `aria-label`
- 颜色对比度审计 + 修复

**验收：**
1. Tab 键可完成：登录 → 导航 → 查看数据
2. 所有 XtBarChart/XtLineChart/XtGaugeChart 有 aria-label
3. axe-core 扫描 0 critical violations

---

## 执行顺序

```
Week 1: F1 (PWA) + F3 (E2E) — 并行
Week 2: F2 (监控) + F4 (移动端精修) — 并行
Week 3: F5 (可访问性)
```

## 完成标志

- [ ] Service Worker active，离线填报可用
- [ ] Playwright 15+ specs 通过
- [ ] 前端错误上报链路通
- [ ] 移动端骨架屏 + 下拉刷新
- [ ] axe-core 0 critical
- [ ] npm run build 无新增 warning
- [ ] 221+ 测试全绿

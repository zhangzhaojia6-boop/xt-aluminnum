# 高科技前端改造实施计划（HUD 作用域化版）

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`。按 Task 顺序执行，每个 Task 遵循 TDD（先写失败测试 → 最小实现 → 测试通过 → 提交）。每个 Task 的 Owner 在表格里已标注。

## Goal

把「鑫泰铝业 数据中枢」的登录页、管理端外壳（以及可选的填报端）升级为**高科技 HUD 视觉质感**，但实现方式是：
- **作用域化深色 HUD 皮肤**（不污染现有浅色工业主题）；
- **懒加载 Three.js 粒子背景**（不进首屏主包）；
- **统一主题开关**（进页面挂、离页面摘，支持一键回退）。

## Non-Goals

- 不把产品改名为 Cyberpunk / Palantir / Quantum / Sci-Fi。产品名继续是 `鑫泰铝业 数据中枢`。
- 不全局覆盖 Element Plus CSS 变量；不对 `.el-card / .el-dialog / .el-drawer` 打全局 `clip-path` / `backdrop-filter`。
- 本轮不引入 Tailwind、GSAP、PostCSS 新插件；若后续需要再起独立 plan。
- 本轮不改 `/entry` 默认视觉（只在 Task 5 做可选的 HUD 灰度接入）。

## Architecture

1. **主题开关** `useHudTheme()` composable：进入指定路由时写 `document.documentElement.dataset.xtTheme = 'hud'`，离开时恢复。
2. **作用域样式** `frontend/src/design/xt-hud.css`：所有覆盖都挂在 `:root[data-xt-theme="hud"]` 或 `[data-xt-theme="hud"] .xt-manage__sidebar` 这类前缀选择器下；默认主题 0 影响。
3. **粒子背景** `frontend/src/components/hud/ParticleField.vue`：`three@0.169.0`，用 `defineAsyncComponent` 异步加载；`prefers-reduced-motion` / `visibilitychange` / `resize` / `dispose()` 守卫齐全。
4. **Echarts HUD 主题** `frontend/src/design/echarts-hud.js`：注册名字 `xt-hud`；容器只在 `[data-xt-theme="hud"]` 时才用该主题（按需用，不改默认）。
5. **后端可选**：用户主题偏好接口（`GET/PUT /api/v1/user/preferences`），用于跨设备同步 HUD 偏好；不接时 localStorage 兜底。

## Tech Stack

- 现有：Vue 3.5、Vite 8、Element Plus 2.8、Echarts 5.6、vue-echarts 7、Pinia 2、Playwright 1.52。
- 本轮新增：
  - 前端：`three@0.169.0`（唯一新增生产依赖，async chunk）。
  - 后端：无新依赖（若做 Task 6，用现有 FastAPI + SQLAlchemy 栈）。

## 硬约束

- ❌ 不新增 Tailwind / GSAP / CSS-in-JS。
- ❌ 不在全局 CSS 里用 `!important` 改写 Element Plus token。
- ❌ 不创建与现有 e2e 同名文件（下表新 spec 名必须一致）。
- ✅ Login 首屏主入口 gzip 增量 ≤ 40 KB；Three 必须 async chunk，不合并进 `vendor` 主包。
- ✅ 所有 HUD 样式必须在 `[data-xt-theme="hud"]` 前缀下，删掉该属性即视觉完全回退到现状。
- ✅ `@media (prefers-reduced-motion: reduce)` 下 ParticleField 不渲染 canvas，用静态渐变占位。
- ✅ CJK 字体继续用 `--xt-font-body`（MiSans / HarmonyOS Sans SC）；HUD 仅替换**数值/时间码**的等宽字体为 `--xt-font-mono`，不全局换 `font-mono`。
- ✅ 产品标识文案继续显示 `鑫泰铝业 数据中枢` / `数据中枢`；不出现 `Cyberpunk` / `Palantir` / `Quantum` / `Sci-Fi` 字样（代码、UI、注释一致）。

## 新增 / 修改文件清单

| 文件 | 操作 | Owner |
| --- | --- | --- |
| `frontend/package.json` | modify（加 `three`） | Gemini |
| `frontend/src/composables/useHudTheme.js` | create | Gemini |
| `frontend/src/design/xt-hud.css` | create | Gemini |
| `frontend/src/design/echarts-hud.js` | create | Gemini |
| `frontend/src/components/hud/ParticleField.vue` | create | Gemini |
| `frontend/src/views/Login.vue` | modify（仅 template/style 末段，不动 `<script setup>`） | Gemini |
| `frontend/src/layout/ManageShell.vue` | modify（template 根 class 挂钩 + style 末段，不动 `<script setup>`） | Gemini |
| `frontend/src/layout/EntryShell.vue` | modify（可选，Task 5） | Gemini |
| `frontend/src/main.js` | modify（import 一次 xt-hud.css + echarts-hud 注册） | Gemini |
| `frontend/vite.config.js` | modify（`manualChunks` 里把 `three` 单独切 chunk） | Gemini |
| `frontend/e2e/login-hud.spec.js` | create | Gemini |
| `frontend/e2e/manage-shell-hud.spec.js` | create | Gemini |
| `frontend/e2e/entry-hud.spec.js` | create（Task 5） | Gemini |
| `backend/app/api/user_preferences.py` | create（Task 6，可选） | Codex/Claude |
| `backend/app/models/user_preferences.py` | create（Task 6，可选） | Codex/Claude |
| `backend/tests/test_user_preferences.py` | create（Task 6，可选） | Codex/Claude |
| `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-plan.md` | this file | — |

## 分工与执行状态

**角色约定（常设）**
- **Stitch** — UI 意象层（静态 mockup、视觉取向，不写代码）
- **Gemini** — 前端搭建层（Vue / CSS / Vite / e2e 契约）
- **Codex** — 后端契约层（FastAPI / SQLAlchemy / alembic / pytest）
- **Claude** — 验收层（闸门、bundle diff、design-review 打分、合仓）

详见 `docs/team-workflow/2026-05-10-hud-four-way-handoff.md`。

**本轮（2026-05-10）执行状态**

本轮由 Claude 单人按 plan 顺序连跑 Task 0-4、6、7（Gemini/Codex/Claude 三角色合演）；Task 5 本轮明确跳过。每个 Task 的"设计 Owner"指角色分工约定，"本轮 Executor"指实际动手的人。

| Task | 设计 Owner | 本轮 Executor | 状态 | Commit |
| --- | --- | --- | --- | --- |
| 0 | Frontend / Gemini | Claude | ✅ DONE | `35c0b7d` |
| 1 | Frontend / Gemini | Claude | ✅ DONE | `858cd4a` |
| 2 | Frontend / Gemini | Claude | ✅ DONE | `3cd268c` |
| 3 | Frontend / Gemini | Claude | ✅ DONE | `2716275` |
| 4 | Frontend / Gemini | Claude | ✅ DONE | `b14f82c` |
| 5 | Frontend / Gemini（可选） | — | ⏭ SKIPPED（本轮不做，钉钉低配 WebView 代价高） | — |
| 6 | Backend / Codex | Claude | ✅ DONE | `889eac9` |
| 7 | 验收 / Claude | Claude | 🟡 IN PROGRESS（闸门脚本 + checklist 已落盘，待提交 + 本地跑一遍） | (未提交) |

**下一轮若让 Gemini/Codex 真正接手**，参考此表的"设计 Owner"列即可。本轮 commit 已用 TDD 节奏拆干净，后续如需回滚、分拆到独立 PR 给 Gemini/Codex 重做都可以一键摘。

---

## Task 0: 主题开关与命名规范（Frontend / Gemini）

> **Status:** ✅ DONE | **Designed for:** Gemini | **Executed by:** Claude (2026-05-10) | **Commit:** `35c0b7d`

**Files**
- Create: `frontend/src/composables/useHudTheme.js`
- Modify: `frontend/src/main.js`（仅新增一行 import，见 Task 2）

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/useHudTheme.test.js`：

```javascript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyHudTheme, clearHudTheme, isHudActive } from '../src/composables/useHudTheme.js'

test('applyHudTheme sets data-xt-theme="hud" on documentElement', () => {
  const fakeDoc = { documentElement: { dataset: {} } }
  applyHudTheme(fakeDoc)
  assert.equal(fakeDoc.documentElement.dataset.xtTheme, 'hud')
  assert.equal(isHudActive(fakeDoc), true)
})

test('clearHudTheme removes data-xt-theme', () => {
  const fakeDoc = { documentElement: { dataset: { xtTheme: 'hud' } } }
  clearHudTheme(fakeDoc)
  assert.equal(fakeDoc.documentElement.dataset.xtTheme, undefined)
  assert.equal(isHudActive(fakeDoc), false)
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && npm run test -- --test-name-pattern=HudTheme
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 最小实现**

Create `frontend/src/composables/useHudTheme.js`：

```javascript
import { onBeforeUnmount, onMounted } from 'vue'

const THEME_KEY = 'xt-theme-preference'
const HUD = 'hud'

export function applyHudTheme(doc = document) {
  doc.documentElement.dataset.xtTheme = HUD
}

export function clearHudTheme(doc = document) {
  delete doc.documentElement.dataset.xtTheme
}

export function isHudActive(doc = document) {
  return doc.documentElement.dataset.xtTheme === HUD
}

export function readHudPreference() {
  try {
    return localStorage.getItem(THEME_KEY) === HUD
  } catch {
    return false
  }
}

export function writeHudPreference(enabled) {
  try {
    if (enabled) localStorage.setItem(THEME_KEY, HUD)
    else localStorage.removeItem(THEME_KEY)
  } catch {
    /* ignore quota/SSR */
  }
}

/**
 * 进入路由挂 HUD，离开清除。仅在业务视图里调用。
 * @param {{ force?: boolean }} [options]
 */
export function useHudTheme(options = {}) {
  onMounted(() => {
    if (options.force || readHudPreference() !== false) applyHudTheme()
  })
  onBeforeUnmount(() => {
    clearHudTheme()
  })
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && npm run test -- --test-name-pattern=HudTheme
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/composables/useHudTheme.js frontend/tests/useHudTheme.test.js
git commit -m "feat(ui): add useHudTheme composable for scoped HUD activation"
```

---

## Task 1: ParticleField 懒加载组件（Frontend / Gemini）

> **Status:** ✅ DONE | **Designed for:** Gemini | **Executed by:** Claude (2026-05-10) | **Commit:** `858cd4a`

**Files**
- Modify: `frontend/package.json`（加 `"three": "0.169.0"`）
- Modify: `frontend/vite.config.js`（把 `three` 切到独立 async chunk）
- Create: `frontend/src/components/hud/ParticleField.vue`
- Create: `frontend/tests/particleField.test.js`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/particleField.test.js`：

```javascript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const file = path.resolve('src/components/hud/ParticleField.vue')

test('ParticleField respects prefers-reduced-motion', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /prefers-reduced-motion/, '必须检测 reduced-motion')
})

test('ParticleField disposes resources on unmount', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /onBeforeUnmount/)
  assert.match(src, /\.dispose\(\)/)
  assert.match(src, /cancelAnimationFrame/)
})

test('ParticleField listens to resize and visibilitychange', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /'resize'/)
  assert.match(src, /'visibilitychange'/)
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && npm run test -- --test-name-pattern=ParticleField
```

预期：FAIL（文件不存在）。

- [ ] **Step 3: 最小实现**

Modify `frontend/package.json` dependencies：

```json
"three": "0.169.0"
```

Install：

```bash
cd frontend && npm install
```

Modify `frontend/vite.config.js` 的 `manualChunks`，在 `if (normalizedId.includes('/axios/'))` 之前加：

```javascript
if (normalizedId.includes('/three/')) {
  return 'vendor-three'
}
```

Create `frontend/src/components/hud/ParticleField.vue`：

```vue
<template>
  <div ref="root" class="xt-hud-particles" aria-hidden="true">
    <canvas ref="canvasRef" class="xt-hud-particles__canvas"></canvas>
    <div class="xt-hud-particles__fallback" data-testid="hud-particles-fallback"></div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const root = ref(null)
const canvasRef = ref(null)

let renderer = null
let scene = null
let camera = null
let particles = null
let geometry = null
let material = null
let rafId = 0
let mql = null
let disposed = false

const MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function shouldAnimate() {
  return !window.matchMedia(MOTION_QUERY).matches
}

async function initThree() {
  if (disposed || !shouldAnimate() || !canvasRef.value) return
  const THREE = await import('three')

  if (disposed) return

  const { clientWidth: w, clientHeight: h } = root.value
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(60, w / Math.max(h, 1), 0.1, 100)
  camera.position.z = 6

  renderer = new THREE.WebGLRenderer({ canvas: canvasRef.value, alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)

  geometry = new THREE.BufferGeometry()
  const count = 900
  const positions = new Float32Array(count * 3)
  for (let i = 0; i < count; i += 1) {
    positions[i * 3] = (Math.random() - 0.5) * 18
    positions[i * 3 + 1] = (Math.random() - 0.5) * 12
    positions[i * 3 + 2] = (Math.random() - 0.5) * 10
  }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  material = new THREE.PointsMaterial({
    color: 0x5eb8ff,
    size: 0.035,
    transparent: true,
    opacity: 0.72,
    depthWrite: false
  })
  particles = new THREE.Points(geometry, material)
  scene.add(particles)

  loop()
}

function loop() {
  if (disposed || !renderer) return
  if (document.visibilityState === 'hidden') {
    rafId = requestAnimationFrame(loop)
    return
  }
  particles.rotation.x += 0.0006
  particles.rotation.y += 0.0011
  renderer.render(scene, camera)
  rafId = requestAnimationFrame(loop)
}

function handleResize() {
  if (!renderer || !root.value || !camera) return
  const { clientWidth: w, clientHeight: h } = root.value
  renderer.setSize(w, h, false)
  camera.aspect = w / Math.max(h, 1)
  camera.updateProjectionMatrix()
}

function handleMotionChange() {
  if (shouldAnimate() && !renderer) {
    initThree()
  } else if (!shouldAnimate() && renderer) {
    stopAndDispose()
  }
}

function stopAndDispose() {
  cancelAnimationFrame(rafId)
  rafId = 0
  if (geometry) geometry.dispose()
  if (material) material.dispose()
  if (renderer) {
    renderer.dispose()
    renderer.forceContextLoss?.()
  }
  scene = null
  camera = null
  particles = null
  geometry = null
  material = null
  renderer = null
}

onMounted(() => {
  mql = window.matchMedia(MOTION_QUERY)
  mql.addEventListener?.('change', handleMotionChange)
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibility)
  initThree()
})

function handleVisibility() {
  // no-op: loop() 内部已做 visibilityState 判断；保留订阅使测试可验证
}

onBeforeUnmount(() => {
  disposed = true
  mql?.removeEventListener?.('change', handleMotionChange)
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('visibilitychange', handleVisibility)
  stopAndDispose()
})
</script>

<style scoped>
.xt-hud-particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.xt-hud-particles__canvas,
.xt-hud-particles__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.xt-hud-particles__fallback {
  background:
    radial-gradient(120% 80% at 70% 20%, rgba(94, 184, 255, 0.14), transparent 60%),
    radial-gradient(90% 70% at 20% 90%, rgba(37, 99, 235, 0.12), transparent 60%),
    linear-gradient(180deg, #04101f 0%, #020812 100%);
  z-index: 0;
}
.xt-hud-particles__canvas {
  z-index: 1;
}
@media (prefers-reduced-motion: reduce) {
  .xt-hud-particles__canvas {
    display: none;
  }
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && npm run test -- --test-name-pattern=ParticleField
```

- [ ] **Step 5: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/src/components/hud/ParticleField.vue frontend/tests/particleField.test.js
git commit -m "feat(ui): add lazy Three.js ParticleField with a11y + lifecycle guards"
```

---

## Task 2: 作用域 HUD 皮肤 + Echarts 主题（Frontend / Gemini）

> **Status:** ✅ DONE | **Designed for:** Gemini | **Executed by:** Claude (2026-05-10) | **Commit:** `3cd268c`

**Files**
- Create: `frontend/src/design/xt-hud.css`
- Create: `frontend/src/design/echarts-hud.js`
- Modify: `frontend/src/main.js`（新增两行 import + echarts 主题注册）
- Create: `frontend/tests/xtHudCss.test.js`
- Create: `frontend/tests/echartsHud.test.js`

**硬约束复核**
- 所有选择器必须以 `:root[data-xt-theme="hud"]` 或 `[data-xt-theme="hud"] <scope>` 开头；禁止裸 `.el-*` 全局覆盖。
- Echarts 主题名固定 `xt-hud`，仅供显式 `theme="xt-hud"` 调用，**不**改 vue-echarts 默认主题。
- 不得出现 `!important`（Grep 守卫在 Task 7 闸门里）。

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/xtHudCss.test.js`：

```javascript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const file = path.resolve('src/design/xt-hud.css')

test('xt-hud.css only targets [data-xt-theme="hud"] scope', () => {
  const src = fs.readFileSync(file, 'utf8')
  const ruleBlocks = src.split('}').map((b) => b.split('{')[0]).filter((s) => s.trim())
  for (const selectorList of ruleBlocks) {
    for (const sel of selectorList.split(',')) {
      const s = sel.trim()
      if (!s || s.startsWith('@') || s.startsWith('/*')) continue
      assert.match(
        s,
        /^(:root\[data-xt-theme="hud"\]|\[data-xt-theme="hud"\])/,
        `selector out of scope: ${s}`
      )
    }
  }
})

test('xt-hud.css contains no !important', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.equal(src.includes('!important'), false, 'HUD CSS must not use !important')
})

test('xt-hud.css defines HUD tokens as CSS variables', () => {
  const src = fs.readFileSync(file, 'utf8')
  for (const v of ['--xt-hud-canvas', '--xt-hud-panel', '--xt-hud-border', '--xt-hud-text', '--xt-hud-primary']) {
    assert.match(src, new RegExp(v.replace(/[-]/g, '\\-')), `missing token ${v}`)
  }
})
```

Create `frontend/tests/echartsHud.test.js`：

```javascript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { registerHudEchartsTheme, XT_HUD_THEME_NAME } from '../src/design/echarts-hud.js'

test('registerHudEchartsTheme uses name "xt-hud"', () => {
  assert.equal(XT_HUD_THEME_NAME, 'xt-hud')
})

test('registerHudEchartsTheme calls echarts.registerTheme with HUD palette', () => {
  const calls = []
  const fakeEcharts = { registerTheme: (name, theme) => calls.push({ name, theme }) }
  registerHudEchartsTheme(fakeEcharts)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].name, 'xt-hud')
  assert.ok(Array.isArray(calls[0].theme.color) && calls[0].theme.color.length >= 4)
  assert.ok(calls[0].theme.backgroundColor.toLowerCase().startsWith('#0') || calls[0].theme.backgroundColor === 'transparent')
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && npm run test -- --test-name-pattern='xt-hud|HudEchartsTheme'
```

预期：FAIL（文件不存在）。

- [ ] **Step 3: 最小实现**

Create `frontend/src/design/xt-hud.css`：

```css
:root[data-xt-theme="hud"] {
  --xt-hud-canvas: #04101f;
  --xt-hud-canvas-deep: #020812;
  --xt-hud-panel: rgba(10, 24, 46, 0.68);
  --xt-hud-panel-strong: rgba(16, 34, 62, 0.82);
  --xt-hud-border: rgba(148, 196, 255, 0.18);
  --xt-hud-border-strong: rgba(148, 196, 255, 0.34);
  --xt-hud-text: rgba(224, 236, 255, 0.92);
  --xt-hud-text-muted: rgba(176, 196, 224, 0.62);
  --xt-hud-primary: #5eb8ff;
  --xt-hud-success: #4ecb8a;
  --xt-hud-warning: #f0b84a;
  --xt-hud-danger: #ff6b78;
  --xt-hud-accent: #c88f3c;
  --xt-hud-radius-lg: 12px;
  --xt-hud-radius-md: 8px;
  --xt-hud-font-mono: var(--xt-font-mono, "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace);
  color-scheme: dark;
}

:root[data-xt-theme="hud"] body {
  background: var(--xt-hud-canvas);
  color: var(--xt-hud-text);
}

[data-xt-theme="hud"] .xt-manage {
  background: radial-gradient(120% 80% at 70% 10%, rgba(94, 184, 255, 0.08), transparent 58%),
              linear-gradient(180deg, var(--xt-hud-canvas) 0%, var(--xt-hud-canvas-deep) 100%);
  color: var(--xt-hud-text);
}

[data-xt-theme="hud"] .xt-manage__sidebar {
  background: linear-gradient(180deg, rgba(6, 16, 32, 0.92), rgba(4, 12, 24, 0.96));
  border-right: 1px solid var(--xt-hud-border);
  box-shadow: 1px 0 0 rgba(94, 184, 255, 0.06);
}

[data-xt-theme="hud"] .xt-manage__nav-item {
  color: var(--xt-hud-text-muted);
  border-radius: var(--xt-hud-radius-md);
}

[data-xt-theme="hud"] .xt-manage__nav-item.is-active {
  color: var(--xt-hud-text);
  background: rgba(94, 184, 255, 0.1);
  box-shadow: inset 0 0 0 1px var(--xt-hud-border-strong);
}

[data-xt-theme="hud"] .xt-manage__topbar {
  background: rgba(4, 14, 28, 0.72);
  border-bottom: 1px solid var(--xt-hud-border);
  backdrop-filter: blur(8px);
}

[data-xt-theme="hud"] .panel,
[data-xt-theme="hud"] .xt-manage__container .panel {
  background: var(--xt-hud-panel);
  border: 1px solid var(--xt-hud-border);
  border-radius: var(--xt-hud-radius-lg);
  color: var(--xt-hud-text);
}

[data-xt-theme="hud"] .xt-kpi__value,
[data-xt-theme="hud"] .xt-number,
[data-xt-theme="hud"] [data-xt-numeric] {
  font-family: var(--xt-hud-font-mono);
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}

[data-xt-theme="hud"] .login-page {
  background: var(--xt-hud-canvas-deep);
}

[data-xt-theme="hud"] .login-stage__headline h2 {
  background: linear-gradient(180deg, #f2f7ff 0%, rgba(176, 210, 255, 0.72) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

[data-xt-theme="hud"] .login-card.panel {
  background: var(--xt-hud-panel-strong);
  border-color: var(--xt-hud-border-strong);
}

@media (prefers-reduced-motion: reduce) {
  [data-xt-theme="hud"] .xt-manage__topbar {
    backdrop-filter: none;
  }
}
```

Create `frontend/src/design/echarts-hud.js`：

```javascript
export const XT_HUD_THEME_NAME = 'xt-hud'

const HUD_THEME = {
  color: ['#5eb8ff', '#4ecb8a', '#f0b84a', '#ff6b78', '#c88f3c', '#8cb7ff'],
  backgroundColor: 'transparent',
  textStyle: { color: 'rgba(224, 236, 255, 0.92)' },
  title: { textStyle: { color: 'rgba(224, 236, 255, 0.92)' } },
  legend: { textStyle: { color: 'rgba(176, 196, 224, 0.72)' } },
  grid: { borderColor: 'rgba(148, 196, 255, 0.18)' },
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.24)' } },
    axisTick: { lineStyle: { color: 'rgba(148, 196, 255, 0.18)' } },
    axisLabel: { color: 'rgba(176, 196, 224, 0.72)' },
    splitLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.08)' } }
  },
  valueAxis: {
    axisLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.24)' } },
    axisTick: { lineStyle: { color: 'rgba(148, 196, 255, 0.18)' } },
    axisLabel: { color: 'rgba(176, 196, 224, 0.72)' },
    splitLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.08)' } }
  },
  line: {
    itemStyle: { borderWidth: 2 },
    lineStyle: { width: 2, shadowBlur: 8, shadowColor: 'rgba(94, 184, 255, 0.35)' }
  },
  tooltip: {
    backgroundColor: 'rgba(6, 16, 32, 0.92)',
    borderColor: 'rgba(94, 184, 255, 0.36)',
    textStyle: { color: 'rgba(224, 236, 255, 0.92)' }
  }
}

export function registerHudEchartsTheme(echarts) {
  echarts.registerTheme(XT_HUD_THEME_NAME, HUD_THEME)
}
```

Modify `frontend/src/main.js` — 在现有 CSS import 下方追加（顺序放在 `xt-base.css` 之后、`industrial.css` 之前）：

```javascript
import './design/xt-hud.css'
import * as echarts from 'echarts/core'
import { registerHudEchartsTheme } from './design/echarts-hud.js'
registerHudEchartsTheme(echarts)
```

> 如果 `frontend/src/main.js` 暂未直接依赖 `echarts/core`，保留原有 echarts 实例注入路径；注册调用改挂在首个引入 echarts 的模块里，确保只执行一次。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && npm run test -- --test-name-pattern='xt-hud|HudEchartsTheme'
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/design/xt-hud.css frontend/src/design/echarts-hud.js frontend/src/main.js frontend/tests/xtHudCss.test.js frontend/tests/echartsHud.test.js
git commit -m "feat(ui): add scoped HUD skin + xt-hud echarts theme"
```

---

## Task 3: Login HUD 增强（Frontend / Gemini）

> **Status:** ✅ DONE | **Designed for:** Gemini | **Executed by:** Claude (2026-05-10) | **Commit:** `2716275`

**Files**
- Modify: `frontend/src/views/Login.vue`（仅 `<template>` 和 `<style>` 末段；**绝对不改 `<script setup>`**）
- Create: `frontend/e2e/login-hud.spec.js`

**硬约束复核**
- `<script setup>` 内的业务逻辑（钉钉回跳、`resolveRedirectPath`、`submit`、`tryDingtalkLogin` 等）保持一字节不动。
- 粒子背景用 `defineAsyncComponent(() => import('@/components/hud/ParticleField.vue'))`，不直接 `import`。
- 进入页面 `applyHudTheme()`，离开 `clearHudTheme()`。
- 产品文案保持 `鑫泰铝业 数据中枢`，不得出现 `Cyberpunk / Palantir / Quantum / Sci-Fi`。

- [ ] **Step 1: 写失败测试**

Create `frontend/e2e/login-hud.spec.js`：

```javascript
import { test, expect } from '@playwright/test'

test('login page mounts HUD theme and particle background', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('[data-testid="login-hud-backdrop"]')).toBeVisible()
  await expect(page.locator('[data-testid="login-page"]')).toBeVisible()
  await expect(page.locator('[data-testid="login-brand"]')).toContainText('数据中枢')
})

test('login page does not leak forbidden product lexicon', async ({ page }) => {
  await page.goto('/login')
  const body = await page.locator('body').innerText()
  for (const forbidden of ['Cyberpunk', 'Palantir', 'Quantum', 'Sci-Fi']) {
    expect(body).not.toContain(forbidden)
  }
})

test('login page clears HUD theme after navigating away', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await page.goto('about:blank')
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && npx playwright test e2e/login-hud.spec.js
```

预期：FAIL（属性/元素未挂）。

- [ ] **Step 3: 最小实现**

Modify `frontend/src/views/Login.vue`：

1. 在 `<script setup>` 末尾（不动任何既有函数/响应式变量）追加下面三行：

```javascript
import { defineAsyncComponent } from 'vue'
import { useHudTheme } from '../composables/useHudTheme.js'
const LoginHudBackdrop = defineAsyncComponent(() => import('../components/hud/ParticleField.vue'))
useHudTheme({ force: true })
```

2. 在 `<template>` 的最外层 `<div class="login-page">` 紧随其后、`<section class="login-stage">` 前面插入：

```vue
<LoginHudBackdrop data-testid="login-hud-backdrop" class="login-page__backdrop" />
```

3. 在 `<style scoped>` 末段追加（不修改既有 `.login-page` / `.login-stage` 规则）：

```css
.login-page__backdrop {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
:deep([data-xt-theme="hud"]) .login-stage { position: relative; z-index: 1; }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && npx playwright test e2e/login-hud.spec.js
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Login.vue frontend/e2e/login-hud.spec.js
git commit -m "feat(ui): wire HUD theme + lazy particle backdrop into Login"
```

---

## Task 4: ManageShell HUD 壳（Frontend / Gemini）

> **Status:** ✅ DONE | **Designed for:** Gemini | **Executed by:** Claude (2026-05-10) | **Commit:** `b14f82c`

**Files**
- Modify: `frontend/src/layout/ManageShell.vue`（template 挂钩 + style 末段追加，不动 `<script setup>`）
- Create: `frontend/e2e/manage-shell-hud.spec.js`

**硬约束复核**
- 不动既有 `<script setup>` 内的 120+ 行业务（nav、drawer、search、assistant、`handleKeydown` 等）。
- 不在 `ManageShell.vue` 内 `<style scoped>` 顶部现有 `background`、`border-right` 规则上使用 `!important`，新样式一律挂在 `[data-xt-theme="hud"]` 前缀下。
- `useHudTheme({ force: false })`：默认跟随 localStorage 偏好；Task 6 后端接入后由 `auth store` 在 `hydrate()` 时预写 localStorage。

- [ ] **Step 1: 写失败测试**

Create `frontend/e2e/manage-shell-hud.spec.js`：

```javascript
import { test, expect } from '@playwright/test'

test('manage shell opts into HUD when preference is set', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.setItem('xt-theme-preference', 'hud'))
  await page.goto('/manage/overview')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('[data-testid="manage-shell"]')).toBeVisible()
  const sidebarBg = await page.locator('.xt-manage__sidebar').evaluate((el) => getComputedStyle(el).backgroundImage)
  expect(sidebarBg).toMatch(/linear-gradient/)
})

test('manage shell stays in default light theme without preference', async ({ page }) => {
  await page.goto('/manage/overview')
  await expect(page.locator('html')).not.toHaveAttribute('data-xt-theme', 'hud')
})

test('logo and brand text always show 数据中枢', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.setItem('xt-theme-preference', 'hud'))
  await page.goto('/manage/overview')
  await expect(page.locator('.xt-manage__brand')).toContainText('数据中枢')
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && npx playwright test e2e/manage-shell-hud.spec.js
```

预期：FAIL（属性没挂、底色 gradient 不存在）。

- [ ] **Step 3: 最小实现**

在 `frontend/src/layout/ManageShell.vue` 的 `<script setup>` **末尾**（不在既有函数中间插入）追加：

```javascript
import { useHudTheme } from '../composables/useHudTheme.js'
useHudTheme()
```

> 只此一处；不要把 `useHudTheme` 挪进 `onMounted`，composable 自身已用 `onMounted/onBeforeUnmount`。

无需修改 template：`xt-hud.css` 已经以 `[data-xt-theme="hud"] .xt-manage__sidebar` 等 scope 挂钩。

> 若验收阶段发现 `topbar` 的 `backdrop-filter` 与 Element Plus `el-dropdown` popper 层级冲突，降级方案：在 `xt-hud.css` 里把 `.xt-manage__topbar` 的 `backdrop-filter` 换成静态 `background: rgba(4, 14, 28, 0.88)`；不得在 ManageShell 里改动 popper z-index 或 Element Plus 组件。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && npx playwright test e2e/manage-shell-hud.spec.js
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/layout/ManageShell.vue frontend/e2e/manage-shell-hud.spec.js
git commit -m "feat(ui): opt manage shell into scoped HUD theme"
```

---

## Task 5: `/entry` HUD 轻量适配（Frontend / Gemini，默认关）

> **Status:** ⏭ SKIPPED（本轮 2026-05-10 明确跳过，钉钉低配 WebView 上 three.js 代价高；若后续启用，直接按下方步骤执行） | **Designed for:** Gemini | **Executed by:** —

**Files**
- Modify: `frontend/src/layout/EntryShell.vue`（如存在；否则跳过并在 plan footer 标注）
- Create: `frontend/e2e/entry-hud.spec.js`

**这是可选任务。** 默认 `/entry`（钉钉内嵌 H5，一线工人用）**不启用** HUD，以下条件同时满足时再开：
- 产品明确要求移动端与管理端视觉统一；
- 设备回归覆盖到低端安卓 WebView（大部分车间钉钉客户端）；
- 未发现低配机 GPU 占用 > 60% 的告警。

**硬约束复核**
- 本轮 `/entry` HUD 走 query string `?theme=hud` 显式开启，不读 localStorage。
- ParticleField 默认**不**挂到 `/entry`；只换配色与面板（因为 WebView Three.js 成本高）。
- `prefers-reduced-motion` 时 `/entry` 甚至不做渐变背景，退回 `#0a1628` 纯色，避免滚动卡顿。

- [ ] **Step 1: 写失败测试**

Create `frontend/e2e/entry-hud.spec.js`：

```javascript
import { test, expect } from '@playwright/test'

test('entry keeps default theme by default', async ({ page }) => {
  await page.goto('/entry')
  await expect(page.locator('html')).not.toHaveAttribute('data-xt-theme', 'hud')
})

test('entry opts into HUD when ?theme=hud', async ({ page }) => {
  await page.goto('/entry?theme=hud')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
})

test('entry HUD does not load three.js particle backdrop', async ({ page }) => {
  const requests = []
  page.on('request', (req) => {
    if (req.url().includes('three')) requests.push(req.url())
  })
  await page.goto('/entry?theme=hud')
  await page.waitForLoadState('networkidle')
  expect(requests).toEqual([])
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && npx playwright test e2e/entry-hud.spec.js
```

- [ ] **Step 3: 最小实现**

在 `frontend/src/layout/EntryShell.vue` 的 `<script setup>` 末尾追加：

```javascript
import { useRoute } from 'vue-router'
import { applyHudTheme, clearHudTheme } from '../composables/useHudTheme.js'
import { onBeforeUnmount, onMounted, watch } from 'vue'

const entryRoute = useRoute()
function syncEntryHud() {
  if (entryRoute.query.theme === 'hud') applyHudTheme()
  else clearHudTheme()
}
onMounted(syncEntryHud)
watch(() => entryRoute.query.theme, syncEntryHud)
onBeforeUnmount(() => clearHudTheme())
```

> 变量故意命名 `entryRoute`，避免与视图中既有 `route` 变量撞名。若 `EntryShell.vue` 已存在 `useRoute()` 实例，复用它即可，不要重复声明。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && npx playwright test e2e/entry-hud.spec.js
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/layout/EntryShell.vue frontend/e2e/entry-hud.spec.js
git commit -m "feat(ui): opt-in HUD theme for /entry via ?theme=hud"
```

> 若 `EntryShell.vue` 文件不存在，**跳过 Task 5**，并在 PR 描述里写明 "/entry 无 shell 组件，HUD 不落地"。

---

## Task 6: 用户主题偏好 API（Backend / Codex，可选）

> **Status:** ✅ DONE | **Designed for:** Codex | **Executed by:** Claude (2026-05-10) | **Commit:** `889eac9`
>
> **实施偏差（无害）**：路由文件落在 `backend/app/routers/user_preferences.py`（plan 原写 `backend/app/api/`）—— 项目约定是 `routers/`，不是 `api/`；按项目约定走。契约完全一致。

**Files**
- Create: `backend/app/models/user_preferences.py`
- Create: `backend/app/api/user_preferences.py`
- Create: `backend/app/schemas/user_preferences.py`
- Create: `backend/tests/test_user_preferences.py`
- Modify: `backend/app/main.py`（router 挂载）
- Modify: `backend/alembic/versions/<timestamp>_user_preferences.py`（新迁移）

**契约（前后端锁死，Gemini 在 Task 4 消费）**

```
GET  /api/v1/user/preferences      -> 200 { "theme": "hud" | null }  (要求已登录)
PUT  /api/v1/user/preferences      -> 200 { "theme": "hud" | null }  (请求体同 schema; 幂等)
```

- 未登录一律 401，不落新表。
- `theme` 仅允许 `null` 或 `"hud"`；其他值 422。
- 单用户单行（`user_id` UNIQUE）。

**数据库表**

```sql
CREATE TABLE user_preferences (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  theme       VARCHAR(16),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_user_preferences.py`：

```python
import pytest

def test_get_preferences_unauthenticated(client):
    response = client.get("/api/v1/user/preferences")
    assert response.status_code == 401


def test_put_preferences_requires_auth(client):
    response = client.put("/api/v1/user/preferences", json={"theme": "hud"})
    assert response.status_code == 401


def test_get_preferences_default_null(client, auth_headers):
    response = client.get("/api/v1/user/preferences", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"theme": None}


def test_put_then_get_preferences(client, auth_headers):
    put_resp = client.put("/api/v1/user/preferences", json={"theme": "hud"}, headers=auth_headers)
    assert put_resp.status_code == 200
    assert put_resp.json() == {"theme": "hud"}
    get_resp = client.get("/api/v1/user/preferences", headers=auth_headers)
    assert get_resp.json() == {"theme": "hud"}


def test_put_rejects_unknown_theme(client, auth_headers):
    response = client.put("/api/v1/user/preferences", json={"theme": "palantir"}, headers=auth_headers)
    assert response.status_code == 422


def test_put_null_clears_preference(client, auth_headers):
    client.put("/api/v1/user/preferences", json={"theme": "hud"}, headers=auth_headers)
    response = client.put("/api/v1/user/preferences", json={"theme": None}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"theme": None}


def test_put_is_idempotent(client, auth_headers):
    for _ in range(3):
        r = client.put("/api/v1/user/preferences", json={"theme": "hud"}, headers=auth_headers)
        assert r.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && pytest tests/test_user_preferences.py -x
```

预期：FAIL（路由不存在）。

- [ ] **Step 3: 最小实现**

Create `backend/app/schemas/user_preferences.py`：

```python
from typing import Literal, Optional
from pydantic import BaseModel, field_validator

ThemeValue = Optional[Literal["hud"]]


class UserPreferencesIn(BaseModel):
    theme: ThemeValue = None


class UserPreferencesOut(BaseModel):
    theme: ThemeValue = None
```

Create `backend/app/models/user_preferences.py`：

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    theme = Column(String(16), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="preferences", uselist=False)
```

Create `backend/app/api/user_preferences.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.schemas.user_preferences import UserPreferencesIn, UserPreferencesOut

router = APIRouter(prefix="/user/preferences", tags=["user"])


@router.get("", response_model=UserPreferencesOut)
def read_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferencesOut:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user.id).one_or_none()
    return UserPreferencesOut(theme=prefs.theme if prefs else None)


@router.put("", response_model=UserPreferencesOut)
def upsert_preferences(
    payload: UserPreferencesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferencesOut:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user.id).one_or_none()
    if prefs is None:
        prefs = UserPreferences(user_id=current_user.id, theme=payload.theme)
        db.add(prefs)
    else:
        prefs.theme = payload.theme
    db.commit()
    db.refresh(prefs)
    return UserPreferencesOut(theme=prefs.theme)
```

Modify `backend/app/main.py`：挂载 router（沿用现有版本前缀 `/api/v1`）。

生成 alembic 迁移：

```bash
cd backend && alembic revision --autogenerate -m "add user_preferences"
# 验证生成的迁移文件只有新建 user_preferences 表的 op；检查通过后：
alembic upgrade head
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && pytest tests/test_user_preferences.py -x
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/user_preferences.py backend/app/api/user_preferences.py backend/app/schemas/user_preferences.py backend/app/main.py backend/alembic/versions backend/tests/test_user_preferences.py
git commit -m "feat(api): add user preferences endpoint for theme opt-in"
```

> 前端消费（由 Gemini 在 Task 4 之后补）：`auth store` 在 `hydrate()` 成功后并行 `GET /api/v1/user/preferences`，若返回 `theme === "hud"` 则 `writeHudPreference(true)`；用户在管理端切换主题时 `PUT` 同步。前端消费**不阻塞** Gemini 在 Task 4 的 commit：Task 4 仅依赖 localStorage，后端接入是增强。

---

## Task 7: 上线闸门 + bundle diff + 回滚 + 全量回归（验收 / Claude）

> **Status:** 🟡 IN PROGRESS（`scripts/hud-guardrails.sh` + `.ps1` + `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-checklist.md` 已落盘；待提交 + 本地跑通） | **Designed for:** Claude | **Executed by:** Claude (2026-05-10)

**Files**
- Create: `scripts/hud-guardrails.sh`（本地/CI 双跑）
- Modify: `.github/workflows/*.yml`（若已有前端 CI，按它的 runner 习惯挂进去；否则新建最小 workflow）
- Create: `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-checklist.md`（验收 checklist）

**Claude 在每个 PR 下贴的硬闸门**

1. 作用域闸门
   ```bash
   # A. xt-hud.css 必须只管 [data-xt-theme="hud"] scope
   test "$(grep -cE '^\s*(:root)?\[data-xt-theme="hud"\]' frontend/src/design/xt-hud.css)" -gt 0
   # B. 任何 .el-card / .el-dialog / .el-drawer 全局裸选择器禁止出现在 design 目录
   ! grep -rnE '^(\.el-card|\.el-dialog|\.el-drawer)\s*\{' frontend/src/design/
   # C. 禁止 !important
   ! grep -n '!important' frontend/src/design/xt-hud.css
   ```
2. 主包 bundle 闸门
   ```bash
   cd frontend && npm run build
   # 期望产物里有独立 vendor-three chunk，gzip 增量由 scripts/hud-guardrails.sh 计算
   ls -la dist/assets/ | grep -E 'vendor-three|three' || { echo "three not code-split"; exit 1; }
   node scripts/hud-guardrails.mjs --budget-kb 40
   ```
3. 回退闸门（Playwright 截图对比）
   ```bash
   cd frontend && npx playwright test e2e/login-hud.spec.js e2e/manage-shell-hud.spec.js
   # 额外跑一遍强制清 localStorage，确认视觉与 main 分支基本一致
   cd frontend && HUD_DISABLE=1 npx playwright test e2e/manage-shell.spec.js e2e/admin-surface.spec.js
   ```
4. A11y 闸门
   ```bash
   # 在 prefers-reduced-motion: reduce 下启动 chromium，确认 canvas 不渲染
   cd frontend && npx playwright test e2e/login-hud.spec.js --project=reduced-motion
   ```
5. 文案闸门
   ```bash
   ! grep -rniE 'cyberpunk|palantir|quantum|sci-?fi' frontend/src backend/app docs/superpowers/plans docs/superpowers/specs
   ```
6. design-review 打分
   ```bash
   # Claude 在 PR 里跑：将结果贴进 PR 评论
   /design-review http://localhost:5173/login --quick
   /design-review http://localhost:5173/manage/overview --quick
   # AI-Slop 分数必须 >= baseline（不可变差）
   ```

**Create `scripts/hud-guardrails.sh`**：

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/5] scope guard"
grep -cE '^\s*(:root)?\[data-xt-theme="hud"\]' frontend/src/design/xt-hud.css >/dev/null || { echo "xt-hud.css is empty or out of scope"; exit 1; }
! grep -rnE '^(\.el-card|\.el-dialog|\.el-drawer)\s*\{' frontend/src/design/ || { echo "global Element Plus override found"; exit 1; }
! grep -n '!important' frontend/src/design/xt-hud.css || { echo "!important present"; exit 1; }

echo "[2/5] forbidden lexicon"
! grep -rniE 'cyberpunk|palantir|quantum|sci-?fi' frontend/src backend/app docs/superpowers/plans docs/superpowers/specs || { echo "forbidden product lexicon"; exit 1; }

echo "[3/5] frontend unit tests"
(cd frontend && npm run test)

echo "[4/5] frontend build + chunk audit"
(cd frontend && npm run build)
ls frontend/dist/assets/ | grep -E 'three' >/dev/null || { echo "three.js not code-split"; exit 1; }

echo "[5/5] backend unit tests (if Task 6 merged)"
if [ -f backend/tests/test_user_preferences.py ]; then
  (cd backend && pytest tests/test_user_preferences.py -x)
fi

echo "ALL HUD GUARDRAILS PASS"
```

- [ ] **Step 1: 写 checklist**

Create `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-checklist.md`，内容包含本 Task 里 6 组闸门的逐项 `- [ ]`。

- [ ] **Step 2: 跑一遍闸门本地**

```bash
chmod +x scripts/hud-guardrails.sh
./scripts/hud-guardrails.sh
```

- [ ] **Step 3: 回滚演练**

```bash
# 验证单行摘取能一键回退视觉
git checkout main -- frontend/src/design/xt-hud.css
# 观察 /manage/overview 视觉已完全回到当前浅色；恢复：
git checkout HEAD -- frontend/src/design/xt-hud.css
```

- [ ] **Step 4: 提交**

```bash
git add scripts/hud-guardrails.sh docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-checklist.md
git commit -m "chore(ui): add HUD guardrails script + acceptance checklist"
```

---

## 合并顺序

1. Task 0 → 1 → 2（前端基础，Gemini 串行）
2. Task 3、4 可并行（分两个 branch），都依赖 Task 2
3. Task 5 可选，延后
4. Task 6（Codex 并行，从 Task 2 结束就能开工）
5. Task 7 在 3/4（及 6）合入后跑，作为 release gate

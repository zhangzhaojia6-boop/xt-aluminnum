# High-Tech Frontend Reform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the data center frontend into a high-tech "Sci-Fi / Palantir" style utilizing 3D particle backgrounds, GSAP animations, and edge-tracking HUD styling, without breaking underlying business logic.

**Architecture:** 
- Foundation: Install Tailwind CSS (for rapid utility styling) + GSAP + Three.js.
- Theme Override: Hijack Element Plus CSS variables with `backdrop-filter: blur`, deep blues, and fluorescent accents. Register a global "Cyberpunk" Echarts theme.
- The Portal: Rewrite `Login.vue` entirely with a vanilla Three.js particle mesh background and GSAP for terminal-style entrance animations.
- The Shell: Refactor `ManageShell.vue` into an angular, sci-fi HUD layout. 

**Tech Stack:** Vue 3, Vite, Tailwind CSS, GSAP, Three.js, Element Plus, Playwright.

---

### Task 1: Engine Initialization (Tailwind, GSAP, Three.js)

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/assets/styles/high-tech.css`
- Modify: `frontend/src/main.js`
- Create: `frontend/e2e/high-tech-setup.spec.js`

- [ ] **Step 1: Write the failing E2E test**

```javascript
// frontend/e2e/high-tech-setup.spec.js
import { test, expect } from '@playwright/test';

test('verifies global high-tech assets are loaded', async ({ page }) => {
  await page.goto('/');
  // Check for the injection of the Tailwind/HUD utility class
  const body = page.locator('body');
  await expect(body).toHaveClass(/xt-cyber-body/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/high-tech-setup.spec.js`
Expected: FAIL (Timeout expecting class `xt-cyber-body`)

- [ ] **Step 3: Write minimal implementation**

```bash
cd frontend && npm install -D tailwindcss postcss autoprefixer
cd frontend && npm install gsap three
cd frontend && npx tailwindcss init -p
```

Update `frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          dark: '#00050B',
          panel: 'rgba(2, 15, 32, 0.65)',
          glow: '#00d2ff',
          alert: '#ff4d4f'
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace']
      }
    },
  },
  plugins: [],
}
```

Create `frontend/src/assets/styles/high-tech.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

.xt-cyber-body {
  @apply bg-cyber-dark text-slate-200 font-sans antialiased;
  min-height: 100vh;
}
```

Modify `frontend/src/main.js` (Add CSS & global class):
```javascript
// Add before mount
import './assets/styles/high-tech.css'
document.body.classList.add('xt-cyber-body')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx playwright test e2e/high-tech-setup.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tailwind.config.js frontend/postcss.config.js frontend/src/assets/styles/high-tech.css frontend/src/main.js frontend/e2e/high-tech-setup.spec.js
git commit -m "chore(ui): initialize three.js, gsap, and tailwind for high-tech overhaul"
```

### Task 2: Cyberpunk Theme Override (Element Plus & Echarts)

**Files:**
- Modify: `frontend/src/design/xt-tokens.css`
- Create: `frontend/src/design/echarts-cyberpunk.js`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Write the failing E2E test**

```javascript
// frontend/e2e/theme-override.spec.js
import { test, expect } from '@playwright/test';

test('echarts and element plus use cyberpunk styling', async ({ page }) => {
  await page.goto('/');
  // Actually test the element plus override via CSS variable injected to root
  const bgColor = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--el-bg-color'));
  expect(bgColor).toContain('rgba(2, 15, 32, 0.4)');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/theme-override.spec.js`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Modify `frontend/src/design/xt-tokens.css` (Append or Replace specific roots):
```css
:root {
  --el-bg-color: rgba(2, 15, 32, 0.4) !important;
  --el-bg-color-overlay: rgba(0, 5, 11, 0.85) !important;
  --el-border-color-light: rgba(0, 210, 255, 0.15) !important;
  --el-text-color-primary: #e2e8f0 !important;
  --el-color-primary: #00d2ff !important;
  --el-border-radius-base: 0px !important; /* Hard cuts for Sci-Fi */
}

/* Glassmorphism for panels */
.el-card, .el-dialog, .el-drawer, .xt-manage__sidebar {
  backdrop-filter: blur(20px);
  border: 1px solid rgba(0, 210, 255, 0.2) !important;
  box-shadow: 0 0 15px rgba(0, 210, 255, 0.05) !important;
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%);
}
```

Create `frontend/src/design/echarts-cyberpunk.js`:
```javascript
import * as echarts from 'echarts';

const theme = {
  color: ['#00d2ff', '#00f2fe', '#4facfe', '#ff0844', '#f5576c'],
  backgroundColor: 'transparent',
  textStyle: { color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace' },
  splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
};

export function registerCyberpunkTheme() {
  echarts.registerTheme('cyberpunk', theme);
}
```

Modify `frontend/src/main.js` to register theme:
```javascript
import { registerCyberpunkTheme } from './design/echarts-cyberpunk.js'
registerCyberpunkTheme()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx playwright test e2e/theme-override.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/design/xt-tokens.css frontend/src/design/echarts-cyberpunk.js frontend/src/main.js frontend/e2e/theme-override.spec.js
git commit -m "feat(ui): inject global cyberpunk overrides for Element Plus and Echarts"
```

### Task 3: Quantum Portal (Login.vue 3D Overhaul)

**Files:**
- Create: `frontend/src/components/ThreeParticleGrid.vue`
- Modify: `frontend/src/views/Login.vue`
- Create: `frontend/e2e/login-3d.spec.js`

- [ ] **Step 1: Write the failing E2E test**

```javascript
// frontend/e2e/login-3d.spec.js
import { test, expect } from '@playwright/test';

test('login page contains webgl canvas and scifi form', async ({ page }) => {
  await page.goto('/');
  const canvas = page.locator('canvas.three-bg');
  await expect(canvas).toBeVisible();
  await expect(page.locator('.cyber-terminal-form')).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/login-3d.spec.js`
Expected: FAIL (Canvas and `.cyber-terminal-form` do not exist)

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/ThreeParticleGrid.vue`:
```vue
<template>
  <div ref="container" class="absolute inset-0 z-[-1] overflow-hidden bg-cyber-dark">
    <canvas ref="canvasRef" class="three-bg"></canvas>
  </div>
</template>
<script setup>
import { onMounted, ref, onBeforeUnmount } from 'vue'
import * as THREE from 'three'

const container = ref(null)
const canvasRef = ref(null)
let scene, camera, renderer, particles

onMounted(() => {
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
  renderer = new THREE.WebGLRenderer({ canvas: canvasRef.value, alpha: true })
  renderer.setSize(window.innerWidth, window.innerHeight)
  
  const geometry = new THREE.BufferGeometry()
  const vertices = []
  for (let i = 0; i < 2000; i++) {
    vertices.push(
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 20
    )
  }
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))
  const material = new THREE.PointsMaterial({ color: 0x00d2ff, size: 0.05 })
  particles = new THREE.Points(geometry, material)
  scene.add(particles)
  camera.position.z = 5

  const animate = function () {
    requestAnimationFrame(animate)
    particles.rotation.x += 0.001
    particles.rotation.y += 0.002
    renderer.render(scene, camera)
  }
  animate()
})
</script>
```

Modify `frontend/src/views/Login.vue` (Surgical UI Edit, DO NOT overwrite script):
Instruct the executing agent to surgically insert `<ThreeParticleGrid />` as the background, and add Tailwind classes `bg-cyber-panel backdrop-blur-xl border border-cyan-500/30 font-mono cyber-terminal-form` to the main login form wrapper. Keep the existing `<script setup>` entirely intact to preserve auth logic.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx playwright test e2e/login-3d.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ThreeParticleGrid.vue frontend/src/views/Login.vue frontend/e2e/login-3d.spec.js
git commit -m "feat(ui): implement vanilla Three.js quantum portal login experience"
```

### Task 4: ManageShell 2.0 (HUD / Sci-fi Shell)

**Files:**
- Modify: `frontend/src/layout/ManageShell.vue`
- Create: `frontend/e2e/manage-shell.spec.js`

- [ ] **Step 1: Write the failing E2E test**

```javascript
// frontend/e2e/manage-shell.spec.js
import { test, expect } from '@playwright/test';

test('manageshell has cyber-hud layout', async ({ page }) => {
  await page.goto('/');
  // Check for the new background class injected on the aside or main container
  const aside = page.locator('aside');
  await expect(aside).toHaveClass(/bg-cyber-panel/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/manage-shell.spec.js`
Expected: FAIL (Class not present)

- [ ] **Step 3: Write minimal implementation**

Modify `frontend/src/layout/ManageShell.vue` (Surgical Edit):
Instruct the executing agent to surgically edit the existing `ManageShell.vue` file. DO NOT overwrite the file. Add `bg-cyber-dark text-slate-300 font-mono` to the root div. Add `bg-cyber-panel backdrop-blur-xl border-cyan-500/20` to the `<aside>` and `<header>` tags. Retain all existing v-for loops, router-links, and the entire `<script setup>` block.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx playwright test e2e/manage-shell.spec.js`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layout/ManageShell.vue frontend/e2e/manage-shell.spec.js
git commit -m "feat(ui): refactor ManageShell into a sci-fi HUD edge-tracking layout"
```

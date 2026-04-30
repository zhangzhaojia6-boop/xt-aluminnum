# 管理端仪表盘视觉收敛 — 设计规格

## 问题诊断

三个仪表盘页面（FactoryDirector、WorkshopDirector、Statistics）存在三套独立的视觉语言：

| 维度 | FactoryDirector | WorkshopDirector | Statistics |
|------|----------------|-----------------|-----------|
| 页面容器 | `ReferencePageFrame` 包裹 | 裸 `div.page-stack` | 裸 `div.page-stack` |
| stat-card 样式 | 共享 `.stat-card`（来自全局） | 共享 `.stat-card` | 自定义 `.stat-card`（独立 fallback 变量） |
| 面板组件 | `el-card` + 自定义 panel | `el-card` + 自定义 panel | `el-card` + 自定义 `.panel` |
| 标题层级 | `h2` 品牌标题 + section-title | `h1` + eyebrow 模式 | `h1` 裸标题 |
| 网格列数 | `repeat(4, minmax(0, 1fr))` | `repeat(auto-fit, minmax(200px, 1fr))` | `repeat(auto-fill, minmax(200px, 1fr))` |
| 动画 | `review-factory-reveal` 渐入 | `review-workshop-reveal` 渐入 | 无动画 |
| 数字字体 | 继承全局 `--xt-font-number` | 继承全局 | 自定义 fallback `'SF Pro Display'` |
| CSS 变量 | 使用 `--xt-*` token | 使用 `--xt-*` token | 使用 `--card-bg`, `--text-muted` 等私有变量 |

核心问题：Statistics 页面完全脱离设计系统，使用私有 CSS 变量和 fallback 值。三个页面的 stat-card、panel、标题、网格各自为政。

## 设计方向

**参考产品：**
- Linear：密集信息仪表盘，stat 卡片用极简 border + 数字突出，无多余装饰
- Vercel Analytics：KPI 网格统一间距，数字用 tabular-nums，标签用 muted 色
- Grafana：多面板 dashboard，统一的 panel 容器 + 一致的 header 模式

**视觉论点：** 克制工业仪表盘——数字是主角，容器退到背景，所有面板共享同一套骨架。

**交互论点：** 统一的 stagger reveal 动画（0.02s 递增），hover 时 card 微升 + border 变色。

## 改造清单

### 1. Statistics.vue — 全面迁移到设计系统

**当前问题：** 使用 `--card-bg`, `--card-border`, `--shadow-card`, `--text-muted`, `--text-main`, `--font-number`, `--radius-card` 等私有变量，与 xt-tokens.css 完全脱节。

**改造内容：**

替换所有私有 CSS 变量为 xt token：

```
--card-bg, #fff           → var(--xt-bg-panel)
--card-border, rgba(...)  → var(--xt-border-light)
--shadow-card, 0 1px ...  → var(--xt-shadow-sm)
--shadow-card-hover, ...  → var(--xt-shadow-md)
--text-muted, #86868b     → var(--xt-text-muted)
--text-main, #1d1d1f      → var(--xt-text)
--font-number, 'SF Pro..' → var(--xt-font-number)
--radius-card, 16px       → var(--xt-radius-xl)
--app-bg, #f5f5f7         → var(--xt-bg-page)
transition: 0.3s          → var(--xt-motion-normal)
```

添加 stagger reveal 动画（复用 WorkshopDirector 的 `@keyframes` 模式）。

stat-value 字号从 `28px` 降到 `24px`（`--xt-text-2xl`），与其他两个页面对齐。

### 2. 三页面 stat-card 统一

**目标：** 三个页面的 `.stat-card` 使用完全相同的样式规则。

**统一规格：**
```css
.stat-card {
  padding: var(--xt-space-4);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-sm);
  transition: transform var(--xt-motion-fast) var(--xt-ease),
              box-shadow var(--xt-motion-fast) var(--xt-ease),
              border-color var(--xt-motion-fast) ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-md);
}

.stat-label {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: var(--xt-space-1);
}

.stat-value {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 700;
  color: var(--xt-text);
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}
```

### 3. 网格列数统一

三个页面的 stat-grid 统一为：
```css
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xt-space-3);
}
```

FactoryDirector 当前用 `repeat(4, ...)` 固定四列，改为 `auto-fit` 响应式。删除其 `@media` 断点覆盖（1280px/1100px），auto-fit 自动处理。

### 4. panel 容器统一

三个页面的 `.panel` / `el-card.panel` 统一为：
```css
.panel {
  padding: var(--xt-space-4);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-sm);
  margin-bottom: var(--xt-space-3);
}
```

### 5. 标题模式统一

- FactoryDirector：保留 `h2` 品牌标题（它是厂级总览，标题层级合理）
- WorkshopDirector：保留 `h1` + eyebrow 模式
- Statistics：`h1` 改为与 WorkshopDirector 相同的 eyebrow + h1 模式：
  ```html
  <div class="page-header">
    <div>
      <div class="page-eyebrow">数据观察</div>
      <h1>统计看板</h1>
    </div>
    ...
  </div>
  ```

### 6. 动画统一

Statistics 添加与 WorkshopDirector 相同的 reveal 动画：
```css
.stat-reveal {
  opacity: 0;
  transform: translateY(8px);
  animation: stat-reveal 0.24s var(--xt-ease) forwards;
}
.stat-reveal--1 { animation-delay: 0.02s; }
.stat-reveal--2 { animation-delay: 0.04s; }
.stat-reveal--3 { animation-delay: 0.06s; }

@keyframes stat-reveal {
  to { opacity: 1; transform: translateY(0); }
}
```

### 7. .note 样式统一

三个页面都有 `.note` 类，统一为：
```css
.note {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
}
```

## 不改的部分

- FactoryDirector 的 `ReferencePageFrame` 包裹——它是厂级页面，有模块编号，保留
- WorkshopDirector 的 `el-collapse` 泳道结构——功能性布局，不动
- FactoryDirector 的 hero 区域（工厂地图、AI 执行链、车间色带）——已经是定制设计，不动
- 各页面的数据获取逻辑和 computed 属性——纯样式改造，不碰 JS

## 验收标准

1. Statistics.vue 中不再出现任何 `--card-bg`, `--card-border`, `--shadow-card`, `--text-muted`, `--text-main`, `--font-number`, `--radius-card` 私有变量
2. 三个页面的 `.stat-card` 视觉完全一致（padding、border、shadow、字号、字体）
3. 三个页面的 `.stat-grid` 使用相同的 `auto-fit` 响应式网格
4. Statistics 有 stagger reveal 动画
5. `npx vite build` 零错误

# 四方协作 SOP：HUD 前端改造（Stitch + Gemini + Codex + Claude）

Date: 2026-05-10
Scope: HUD 作用域化前端改造（见 `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-plan.md`）
Owner: 项目负责人

---

## 0. 为什么要分四层

一个人（或一个模型）包办前端美学 + 前端实现 + 后端契约 + 验收，容易出现三类错误：

1. 视觉方向摇摆（同一次对话里换了三次色板）
2. 实现跑偏但没人兜底（加了 Tailwind 还号称"作用域化"）
3. 不跑闸门就合并（bundle 多 400KB 没人发现）

四方分工把这三件事切成独立决策点：

- **Stitch** 决定"长什么样"
- **Gemini** 决定"代码怎么写"（前端）
- **Codex** 决定"后端契约怎么兜"
- **Claude** 决定"能不能合"

---

## 1. 角色定义与红线

### 1.1 Stitch（UI 意象层）

**职责**
- 产出 3-5 张静态 mockup：Login 全屏、Manage 首屏、KPI 条单卡、抽屉详情、（可选）Entry HUD 变体
- 每张图带 "visual note"：色板取值、排版节奏、关键交互亮点

**不做**
- 不生产代码（不给 HTML/CSS/JSX）
- 不决定依赖栈
- 不写 design token 表（交给 Claude 从 mockup + 现有设计稿综合落地）

**交付路径**
- `docs/design-references/2026-05-10-hud/stitch-*.png`
- 同目录 `stitch-notes.md`，每张图 5-10 行 note

**红线**
- 不得出现紫蓝渐变 orbs、玻璃拟态卡片堆、三栏对称 feature 卡（AI-slop 特征）
- 必须符合 `docs/superpowers/specs/2026-05-10-manage-shell-dark-command-center-design.md` 第 4 节视觉方向："深海工业指挥台"
- 文案一律 `鑫泰铝业 数据中枢`；不出现 Cyberpunk / Palantir / Quantum / Sci-Fi

### 1.2 Gemini（前端实现层）

**职责**
- 按 `high-tech-frontend-reform-plan.md` 的 Task 0 → 1 → 2 → (3∥4) → (5?) 顺序串/并行执行
- 每个 Task 一个独立 branch + PR
- TDD 顺序不可打乱：先失败测试，再最小实现，再跑通测试，最后 commit

**不做**
- 不改 `.el-card / .el-dialog / .el-drawer` 全局样式
- 不引入 Tailwind / GSAP / CSS-in-JS（硬约束）
- 不改后端路由，不改业务 `<script setup>` 逻辑
- 不在一个 PR 里塞多个 Task

**交付路径**
- Branch 命名：`gemini/hud-task-<N>-<slug>`，如 `gemini/hud-task-3-login`
- PR 描述必须包含：对应 Task 号、三个 before/after 截图、`npm run test` 和对应 Playwright spec 的通过截图

**红线**
- PR 里出现新生产依赖而 Task 清单未列出 → Claude 直接拒
- PR 里 `<script setup>` 被动到非新增的现有行 → Claude 直接拒
- bundle 里 `three` 没切出独立 chunk → Claude 直接拒

### 1.3 Codex（后端契约层）

**职责**
- 执行 Task 6：`user_preferences` model + API + schema + 迁移 + 测试
- 契约严格锁死为 plan Task 6 中的定义：`GET/PUT /api/v1/user/preferences`，`theme: "hud" | null`

**不做**
- 不碰 `frontend/`
- 不给自己加新端点（比如 "ai-highlight-color" 之类的扩展）
- 不动 `users` 表结构（只新建 `user_preferences`）

**交付路径**
- Branch：`codex/hud-task-6-user-preferences`
- PR 必须包含：alembic 迁移文件、`pytest tests/test_user_preferences.py` 全绿截图、手动 curl 两条路径的输出

**红线**
- 迁移文件里包含非 `user_preferences` 表的操作 → Claude 拒
- 测试里出现跳过/xfail → Claude 要求理由才放行
- 契约字段名变动（大小写、命名风格）→ 回退

### 1.4 Claude（验收层，我）

**职责**
- 把 Stitch 的视觉意象 + 两份深色 HUD 设计稿综合成"HUD 执行设计稿 v1"（落在 plan Task 2 的 token 表里，已完成）
- 对 Gemini、Codex 每一个 PR 跑 `scripts/hud-guardrails.sh`，贴 checklist 评论
- 跑 `/design-review` 给 baseline 和每个 PR 打分
- 冲突仲裁：当 Gemini 和 Codex 契约理解不一致，以本 SOP 的 Task 6 契约为准
- 合仓：所有闸门绿，Claude 执行 squash merge

**不做**
- 不主动替 Gemini 写 Vue 代码（Gemini 卡住时给反馈 + 最多 patch 一个文件，不包场）
- 不替 Codex 写 Python 代码（同上）
- 不在没跑完闸门的情况下合并

**红线**
- 哪怕 Gemini/Codex 都说"小改一下很快"，只要闸门不过就不合
- 我自己若在验收过程中顺手动了实现代码，当场切 branch 变成 Gemini/Codex 的工单，不混入验收 PR

---

## 2. 流水线时序

```
T+0  Stitch 交付 3-5 张 mockup
T+0.5 Claude 综合 mockup + 两份设计稿，确认 plan Task 2 的 token 表
     （如 token 要调，改 xt-hud.css 的默认值，不改结构）
T+1  Gemini 开 Task 0 → 1 → 2 串行；Codex 开 Task 6 并行（两者互不阻塞）
T+2  Gemini Task 3、4 并行（各自 branch）
T+3  （可选）Gemini Task 5
T+4  Claude 跑 Task 7 闸门 + /design-review
T+5  全部合仓
```

"T+N" 是逻辑先后，不是日历天。

---

## 3. PR 模板（四方通用）

```markdown
### Task
Task <N>: <名称>，引用 docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-plan.md

### 改动摘要
<一句话>

### 闸门自检（Gemini / Codex 自己先跑）
- [ ] 本 Task 的 Step 2 失败测试输出（贴摘要）
- [ ] 本 Task 的 Step 4 通过测试输出（贴摘要）
- [ ] `./scripts/hud-guardrails.sh` 通过（若脚本已落地）
- [ ] 不引入本 Task 未列入的新依赖
- [ ] 产品文案无禁用词

### 验收需要的输入
- 前端任务：before/after 截图，至少 desktop + mobile
- 后端任务：`curl` 两条路径（200 + 401）输出

### Claude 验收区（Claude 填）
- [ ] 作用域闸门
- [ ] Bundle 闸门
- [ ] 回退闸门
- [ ] A11y 闸门
- [ ] 文案闸门
- [ ] /design-review 分数对比
```

---

## 4. 协作红线（所有方共同遵守）

1. **一个 PR 一个 Task。** 不允许"顺手把 Task N 的小 bug 也修了"。
2. **契约一次锁死。** Task 6 的契约字段在合入后不允许改名/改类型；任何扩展走新 PR 新契约。
3. **反悔机制走 plan。** 如果 Gemini 或 Codex 发现 plan 有错，不在 PR 里"偷偷改"，而是开一个 plan 修订 PR 先合，再开实现 PR。
4. **时序不可反。** Task 2 没合，Task 3/4 不开始（不然 xt-hud.css 还不存在，测试跑不了）。
5. **回滚优先于硬扛。** 若 Task N 合后发现线上出问题，第一反应是 `git revert`，不是补热修。HUD 整套设计就是为"可一键回退"服务的。

---

## 5. Prompt 模板

### 5.1 给 Stitch

> 我要为一个中国铝业工厂的"数据中枢"管理后台设计 UI 意象。这是一个 **工业控制台 / 深海指挥台** 风格的产品，不是 SaaS landing。
>
> 请给我 4 张 1440×900 的 mockup：
>
> 1. Login 全屏：左侧品牌 + 工厂全景地图 + 三个角色入口按钮；右侧登录卡片。背景是深色（近黑蓝）带非常微弱的粒子质感，不要紫蓝 blur orbs。
> 2. Manage 首屏：252px 左侧深色导航（8 个一级模块图标+文字），顶部状态带（模块标题 + 搜索 + AI助手 + 用户菜单），中央 KPI 条（4-6 个数字卡），右侧事件/AI 侧栏，底部细运行状态条。
> 3. KPI 单卡：数字用等宽字体，标签退后，状态色用细的胶囊标签。
> 4. 抽屉详情：右滑 420px 宽，标题 + 分段信息 + 操作按钮。
>
> 硬禁止：
> - 不用紫蓝渐变、玻璃拟态、blur orbs、SaaS 三卡片 feature 网格
> - 不用 Papyrus/Comic Sans/Lobster
> - 文案必须是中文，品牌 "鑫泰铝业 数据中枢"
> - 不出现 Cyberpunk / Palantir / Quantum / Sci-Fi 字样

### 5.2 给 Gemini（以 Task 3 为例）

> 你现在执行 `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-plan.md` 的 Task 3：Login HUD 增强。
>
> 硬约束（违反即 PR 会被拒）：
> 1. 不动 `frontend/src/views/Login.vue` 的 `<script setup>` 任何**既有行**，只可在末尾追加 import + 3 行 composable 调用。
> 2. 新组件 `LoginHudBackdrop` 必须 `defineAsyncComponent`，不能直接 import。
> 3. 先写 `frontend/e2e/login-hud.spec.js`，跑一次让它红，再改 Login.vue 让它绿，最后 commit。
> 4. commit 信息：`feat(ui): wire HUD theme + lazy particle backdrop into Login`
>
> 交付：
> - Branch `gemini/hud-task-3-login`
> - PR 描述含 before/after 截图 + `npx playwright test e2e/login-hud.spec.js` 输出摘要

### 5.3 给 Codex（Task 6）

> 你执行 `docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-plan.md` 的 Task 6。
>
> 契约（不得改）：
> ```
> GET  /api/v1/user/preferences   -> 200 {"theme": "hud" | null}
> PUT  /api/v1/user/preferences   -> 200 {"theme": "hud" | null}
> ```
> 未登录 401；theme 非法 422。
>
> 顺序：
> 1. 先写 `backend/tests/test_user_preferences.py`（7 个 case，见 plan）
> 2. 跑 pytest 让它红
> 3. 加 model + schema + router + migration
> 4. 跑 pytest 让它绿
> 5. commit `feat(api): add user preferences endpoint for theme opt-in`
>
> Branch `codex/hud-task-6-user-preferences`。
>
> 不要做的事：不给前端写任何消费代码；不改 `users` 表；不扩展到其他 preference 字段。

### 5.4 给 Claude（验收）

> 验收 PR #<N>（Task <K>）。
>
> 步骤：
> 1. Checkout 分支
> 2. 跑 `./scripts/hud-guardrails.sh`
> 3. 跑 `/design-review` 对比 baseline
> 4. 按 PR 模板的 "Claude 验收区" 逐项打钩
> 5. 贴评论，给 approve / request changes
> 6. 若 approve：等作者确认后 squash merge

---

## 6. 风险与回退

| 风险 | 触发条件 | 应对 |
|---|---|---|
| three.js 在低配机掉帧 | 合后 2 周内任何 Sentry FPS < 30 报警 | `git revert` Task 1；HUD 改用静态 SVG 粒子占位 |
| Element Plus popper z-index 冲突 | 下拉被 backdrop-filter 截断 | 在 `xt-hud.css` 里移除 `.xt-manage__topbar` 的 `backdrop-filter`；不动 popper |
| 后端迁移失败 | Task 6 合入后 alembic upgrade 报错 | `alembic downgrade -1`；Codex 修 `op.create_table` 语法 |
| AI-slop 分数回退 | /design-review 给出比 baseline 低 | 不合；打回对应 Task 作者修视觉 |
| 前端测试 flaky | Playwright e2e 偶发失败 | 不吞；作者加 `await page.waitForLoadState`，不得加 `retries` |

---

## 7. 开工前最后确认

项目负责人在 Stitch 出图前确认以下三条，再启动流水线：

- [ ] 确认 plan A 执行，plan B（aesthetic-dynamic-landing）归档（建议写在 plan B 顶部一行 `> Status: superseded by 2026-05-10-high-tech-frontend-reform-plan.md`）
- [ ] 确认 Task 5（/entry HUD）本轮**不**做，或明确做
- [ ] 确认 Task 6（后端偏好）本轮**做**，Codex 能开工

三条任一 NO，回到方案讨论。

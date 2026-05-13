# 鑫泰铝业工业 AI 协同平台 · Codex 分阶段 Goal 提示词

**Date:** 2026-05-13
**Owner:** 张兆钾 / Claude 验收
**Scope:** 把现有仓库（大量半成品 + 已部署云试运行 + 21 张高清参考图）收口成可试运行、可继续迭代的现代工业 AI 生产中枢。

## 阅读顺序

1. 先读本文件的"横切约束"和"并行编排"两节 —— 所有 phase 都受它们约束。
2. 再按 Phase 0 → 1 → 1.5 → 2 → 3 → 4 → 5 → 6 → 7 → 8 顺序理解依赖图。
3. 用时直接复制对应 Phase 的 prompt，丢给：
   ```
   codex exec "<prompt>" -C "D:\zzj Claude code\aluminum-bypass" \
     -s workspace-write -c model_reasoning_effort="high"
   ```

## 背景现状（直接读不用查）

- **高清参考图基线**：`docs/ui-reference/highres/01..21-*.png`，1672×941，总量 ≤ 5.6 MB。基线文档 `docs/ui-reference/REFERENCE_MANIFEST.md`。
- **已有 UI 目标文档**（不是空的，都要校准不是新建）：
  - `docs/ui-reference/UI_TARGET_SPEC.md`（113 行）
  - `docs/ui-reference/IMAGE2_PROMPTS.md`（175 行）
  - `docs/ui-reference/DESIGN_REVERSE_PLAN.md`（166 行）
- **前端页面目录**：`frontend/src/views/{ai,attendance,dashboard,energy,entry,executive,factory-command,imports,master,mobile,quality,reconciliation,reports,review,shift,team}` + `Login.vue`。
- **后端 routers**：33 个（从 ai 到 work_orders 全覆盖）；`services/` 已沉淀 20+ service（`daily_production_canonical_service`、`daily_energy_report_service`、`ai_briefing_service`、`anomaly_detection_service`、`audit_service` 等）。
- **真实生产样本**：`D:\鑫泰报表\4.20..5.5\` 每日归档 Excel，含"鑫泰每日产量5月.xls"、"5月份各车间成品率.xlsx"、"能耗统计表.xls"、"河南鑫泰合同报表.xlsx"。
- **HUD 视觉已就位**：`frontend/src/design/xt-hud.css`、`useHudTheme`、`echarts-hud`（xt-hud 主题已注册），`ParticleField` 懒加载。
- **用户偏好 API 就位**：`GET/PUT /api/v1/user/preferences`，契约 `{theme: "hud"|null}`。
- **已知线上风险（来自前轮审计）**：填报→管理端可见性问题 + 管理端产量显示 ~10w 异常 → 见 `docs/audits/2026-05-12-live-fill-mes-binding-audit.md`。

## 横切约束（每个 Phase 都必须遵守）

### A. 开工前必读

- `CLAUDE.md`（项目协作规则）
- `AGENTS.md`（Codex 协作规则）
- `DESIGN.md`（视觉硬规则）
- `docs/ui-reference/REFERENCE_MANIFEST.md`（高清图基线）
- 本 phase 所在目录的 `README.md`（若存在）

### B. 开工前必写

**每个 phase 启动前，先在 `docs/superpowers/audits/2026-05-13-<phase-slug>-kickoff.md` 登记：**
- 本 phase 的目标一句话
- 目前已有的资产（文件、endpoint、组件）
- 本 phase 将要创建/修改/删除的文件清单
- 与其他 phase 的依赖点（上游 / 下游）

### C. 收工前必交

- `git status --porcelain` 输出粘到 PR 描述
- `docs/superpowers/audits/2026-05-13-<phase-slug>-done.md`：交付物清单 + 未解决问题 + 下一步建议
- 本 phase 对应的测试全绿（pytest + npm run test），未绿必须在 done.md 说明原因
- 本 phase 动过的代码路径跑一遍 HUD guardrails：`./scripts/hud-guardrails.sh`（或 `.ps1`）

### D. 不得做的事（全局）

- 不得直接 `DELETE FROM` 生产库；任何数据清洗走 `scripts/clean_*.py --dry-run` 流程
- 不得 `--force` 推分支；不得 `--no-verify` 跳 hook
- 不得引入新前端依赖（已有 vue 3.5 / element-plus / echarts / @vueuse/core / dayjs / three / axios / pinia）
- 不得把 `D:\鑫泰报表` 下的 Excel 原件 commit 进 repo；只抽取字段定义到 md
- 不得在 router 里写业务公式；加工一律走 `backend/app/services/` 或 `backend/app/domain/calculators/`
- 不得在 `.vue` 里写数据加工；一律走 composable 或后端
- 不得使用禁用词：`cyberpunk / palantir / quantum / sci-fi / 紫蓝渐变 / 玻璃拟态 / SaaS 三卡片 / emoji 装饰`
- 不得写假数据 / 假字段 / 假图表；所有 KPI 必须有真实数据源或标注 "等待接入"

### E. 真实可信数据的定义

一个数据点可信，当且仅当：
1. 在 `backend/app/domain/calculators/*.py` 里有对应函数 + docstring 标注口径来源
2. 在 `backend/app/schemas/*.py` 里有对应 Pydantic 字段 + 单位声明
3. 在 `backend/tests/test_*.py` 里至少有一条基于真实 Excel 抽样的断言
4. 前端展示时必须在 tooltip 或角标里可以查到"数据来自 XXX / 口径为 XXX / 上次刷新于 XXX"

---

## 并行编排（关键）

### 依赖图

```
Phase 0 ──┐
Phase 1 ──┼─── 只读并行 ───> Phase 3 (救火)
Phase 1.5 ┘                      │
Phase 2 ───────────────────>─────┤
                                 ▼
                               Phase 4 (组件库)
                                 │
                                 ▼
              ┌──────── Phase 5 (三驾驶舱) ────────┐
              │                                     │
              ▼                                     ▼
         Phase 6 (移动+审核)               Phase 7 批 1 (生产闭环)
              │                                     │
              │              ┌──── Phase 7 批 2 (经营)
              │              │
              │              └──── Phase 7 批 3 (AI)
              │              │
              └──────────────┴────> Phase 8 (联调+精修+部署)
```

### 推荐并行组合

**Round 1（只读，100% 可并行 3 个 Codex 终端）：**

| 会话 | Phase | 允许写的目录 |
|---|---|---|
| A | Phase 0 | `docs/ui-reference/` |
| B | Phase 1 + 1.5 | `docs/superpowers/audits/`, `docs/deploy/missing-inputs.md` |
| C | Phase 2 | `backend/app/domain/**`, `backend/tests/test_calculators.py`, `docs/domain/**` |

三会话都使用 `-s workspace-write`，但在 prompt 头部硬性声明"仅允许写下列目录"，不许越界。

**Round 2（救火阶段，独占）：**

| 会话 | Phase | 允许写的目录 |
|---|---|---|
| A | Phase 3 | `backend/app/services/**`, `backend/app/routers/**`, `backend/tests/**`, `scripts/clean_*.py`, `docs/superpowers/audits/` |

**Round 3（Phase 4 组件库独占一次，不并行）：**

| 会话 | Phase | 允许写的目录 |
|---|---|---|
| A | Phase 4 | `frontend/src/components/**`, `frontend/tests/**` |

**Round 4（页面开发 3 路并行）：**

| 会话 | Phase | 允许写的目录 |
|---|---|---|
| A | Phase 5 | `frontend/src/views/dashboard/**`, `frontend/src/views/factory-command/**`, `frontend/src/views/executive/**`, 对应 e2e |
| B | Phase 6 | `frontend/src/views/mobile/**`, `frontend/src/views/review/**`, 对应 e2e |
| C | Phase 7 批 1（生产+库存+能耗）| `frontend/src/views/quality/**`, `frontend/src/views/energy/**` + 对应后端 |

**Round 5（Phase 8 收口，独占）**

### 风险与应对

- **风险 1**：Codex 在 `git add .` 时扫到别的目录。
  应对：每会话 prompt 头尾都要求只 `git add <列表>`，收工前粘 `git status --porcelain` 人工审。
- **风险 2**：两个并行会话同时改 `docs/superpowers/audits/` 造成 merge conflict。
  应对：每会话 kickoff 文件固定 slug，done 文件固定 slug，文件名不冲突。
- **风险 3**：Phase 1 审计发现的问题指向 Phase 2 的口径，而 Phase 2 还在并行跑。
  应对：Phase 1 结束时在 done.md 列"给 Phase 2 的建议"；Phase 2 完工时读一眼再合。

---

## Phase 0 · 设计锚点校准（不是新建）

**Status:** TODO | **Designed for:** Stitch / Claude | **Allowed write paths:** `docs/ui-reference/`

### 前置依赖

- 无。此阶段只读 + 改 md。可在 Round 1 与 Phase 1、Phase 2 并行。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的设计审计员。只许写 docs/ui-reference/ 目录下的文件，任何其他路径一律不许动。

开工前读：
1. docs/ui-reference/REFERENCE_MANIFEST.md（高清图基线）
2. docs/ui-reference/UI_TARGET_SPEC.md（已有 113 行）
3. docs/ui-reference/IMAGE2_PROMPTS.md（已有 175 行）
4. docs/ui-reference/DESIGN_REVERSE_PLAN.md（已有 166 行）
5. docs/ui-reference/highres/ 下所有 png 文件名（先不看图，看清单）
6. DESIGN.md 与 CLAUDE.md

目标：把四份 md 校准到"随便挑一张 highres 图，读者能从三份 md 里精确手搓出 wireframe + 生图 prompt + 代码路径"的程度。不是新建，是补缺补错。

必做：
1. 对 docs/ui-reference/highres/ 下每张 png（01..21），检查：
   - UI_TARGET_SPEC.md 里是否有对应小节（标题要含该中心名）
   - IMAGE2_PROMPTS.md 里是否有对应 prompt 且具体到色板（必须含 #04101f / #020812 / #5eb8ff / #4ecb8a / #f0b84a / #ff6b78 / #c88f3c）
   - DESIGN_REVERSE_PLAN.md 里是否有该页对应的 Vue 组件落点（frontend/src/views/... 或 frontend/src/components/xt-.../...）
   缺一项记 TODO，并当场补齐。

2. 生成新文件 docs/ui-reference/GAP_MATRIX.md，表头为：
   | 图号 | 文件名 | 中心名 | 当前实现路径 | 实现状态 | 三条最大差距 |
   |---|---|---|---|---|---|
   实现状态枚举：未开工 / 半成品 / 收敛中 / 达标
   三条差距用人话写："缺 KPI 同环比小行 / 能耗趋势图缺 ECharts xt-hud 主题 / 登录页缺粒子背景"

3. 对每张 png，若 UI_TARGET_SPEC.md 的小节缺以下字段，补齐：
   - 首屏布局（栅格比例，如 7:3）
   - 组件清单（用到哪些 xt-layout/xt-data/xt-chart/xt-form 组件）
   - 数据源（对应后端 endpoint 占位或真实路径）
   - 空态文案
   - 响应式断点（桌面 1440+ / 平板 1024+ / 移动 375+）
   - 性能预算（首屏 KPI API 调用上限 3 个，chunk gzip ≤ 80 KB）

4. 对每张 png，若 IMAGE2_PROMPTS.md 的 prompt 没有明确说明以下要素，补齐：
   - 画面主体（一句话）
   - 色板（至少 5 个 hex）
   - 布局结构（头部 / 侧栏 / 主区 / 抽屉 比例）
   - 数据密度（信息量级，如"6 KPI + 1 趋势 + 1 时间线"）
   - 组件清单（按 xt-* 前缀）
   - 禁用项（紫蓝渐变 / 玻璃拟态 / SaaS 三卡片 / emoji / papyrus / comic sans）
   - 中文品牌锚点"鑫泰铝业 数据中枢"

5. 对每张 png，若 DESIGN_REVERSE_PLAN.md 指向的 Vue 组件路径不存在（Glob 确认一遍），把路径改成 TODO 标记并在 GAP_MATRIX.md 里打"未开工"。

硬约束：
- 不写代码，不改任何 .vue / .js / .css / .py
- 不新建除 GAP_MATRIX.md 之外的顶层 md
- 不引用禁用词
- 补写的字段必须具体到数字或 hex 或路径，不许"大致"/"可能"

交付：
- GAP_MATRIX.md（新建，≥ 21 行内容）
- UI_TARGET_SPEC.md / IMAGE2_PROMPTS.md / DESIGN_REVERSE_PLAN.md 的 diff（修正不少于 15 处）
- docs/superpowers/audits/2026-05-13-phase-0-done.md（本 phase 交付清单 + 未解决项 + 下一步）

验收：
- 随便挑第 N 号高清图，读者仅凭三份 md 能精确说出：画面是什么、用哪些组件、对应哪个 endpoint、差距在哪
- GAP_MATRIX.md 里"三条最大差距"必须是可 actionable 的（不是"还需优化"这种）

提交：
git add docs/ui-reference/GAP_MATRIX.md docs/ui-reference/UI_TARGET_SPEC.md docs/ui-reference/IMAGE2_PROMPTS.md docs/ui-reference/DESIGN_REVERSE_PLAN.md docs/superpowers/audits/2026-05-13-phase-0-done.md
git commit -m "docs(ui-reference): calibrate UI target spec + image2 prompts against 21 highres references

- Add GAP_MATRIX.md as single source of truth for implementation status
- Fill in grid ratios / component list / data source / empty copy / responsive breakpoints per center
- Normalize image2 prompts to include palette + density + component list + forbidden items
- Mark unimplemented Vue component paths as TODO"

收工前粘贴 git status --porcelain 的输出到本次 Codex 返回文本里，供人工审核是否越界写了其他目录。
```

---

## Phase 1 · 现状审计（只读）

**Status:** TODO | **Designed for:** Claude | **Allowed write paths:** `docs/superpowers/audits/`

### 前置依赖

- 无。Round 1 与 Phase 0、Phase 2 并行。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的代码审计员。只许写 docs/superpowers/audits/ 目录下的 md 文件，任何代码一律不改。

开工前读：
1. CLAUDE.md / AGENTS.md / DESIGN.md
2. docs/ui-reference/REFERENCE_MANIFEST.md
3. docs/superpowers/plans/2026-05-13-codex-staged-goals.md（本 plan）
4. docs/audits/2026-05-02-cleanup-round2-test-audit.md 与 docs/audits/2026-05-12-live-fill-mes-binding-audit.md（前轮审计）

目标：把当前仓库"有什么 / 缺什么 / 烂在哪"摸清楚，产出单一审计报告。

必做：
1. git log --oneline -80：理解近三周改动主线
2. 扫 backend/app/routers/*.py：产出 endpoint 清单表（方法 / 路径 / 入参 / 是否带时间范围 / 是否有权限检查 / 是否有 pytest 覆盖）
3. 扫 backend/app/models/*.py：产出数据模型时间字段矩阵（表名 / business_date 或 created_at 等时间列 / 是否有索引 / 是否有 data_status / 外键）
4. 扫 backend/app/services/*.py：列出所有 service 及其负责的业务（一句话）
5. 扫 frontend/src/views/**/*.vue：产出页面清单表（路由路径 / 对应 role / 视觉层级：HUD / 工业浅色 / 空白 / 混乱 / 半成品）
6. 扫 docs/superpowers/plans/：把 open / superseded / done 三态标出（以最近 commit 时间为辅助判据）
7. 识别矛盾 / 坏味 / 高优先修复项（按影响排序）

产出单一文件：docs/superpowers/audits/2026-05-13-status-audit.md

章节：
- A. 后端 endpoint 清单（表格）
- B. 数据模型时间字段矩阵（表格）
- C. services 层职责分工（列表）
- D. 前端页面清单（表格）
- E. 未解规划清单（表格，标 open/superseded/done）
- F. 发现的矛盾 / 坏味 / 高优先修复项（按影响排序，至少 15 条）
- G. 下一阶段必做 vs 可延后
- H. 给 Phase 2（鑫泰口径）的线索（至少 3 条）
- I. 给 Phase 3（救火）的线索（至少 3 条）

硬约束：
- 只读，不改代码，不跑 migration，不跑 seed
- 禁止用"大致 / 可能 / 应该 / 或许"等模糊词
- 每条判断必须附 文件:行号 证据（形如 backend/app/routers/production.py:42）
- F 节每条问题必须标：影响面（高/中/低）+ 触发条件 + 预期修复工时（小时）

交付：docs/superpowers/audits/2026-05-13-status-audit.md + docs/superpowers/audits/2026-05-13-phase-1-done.md
验收：F 节 ≥ 15 条，每条有证据链接；H/I 节给 Phase 2/3 的线索互不重复
提交：docs(audit): status audit 2026-05-13 for Phase 2/3 handoff
收工前粘贴 git status --porcelain。
```

---

## Phase 1.5 · 云端原系统逆向

**Status:** TODO | **Designed for:** Claude | **Allowed write paths:** `docs/audits/`, `docs/deploy/missing-inputs.md`

### 前置依赖

- 无。Round 1 与 Phase 0、Phase 1 并行（但 1.5 会在缺访问凭证时停下等输入）。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的线上系统逆向审计员。只许写 docs/audits/ 和 docs/deploy/missing-inputs.md。

开工前读：
1. docs/deploy/current-state.md
2. docs/deploy/runbook.md
3. docs/legacy-historical-data-gap-review-2026-04-08.md
4. docs/audits/2026-05-12-live-fill-mes-binding-audit.md
5. docs/mes-api-sync-contract-phase1.md 与 docs/mes-field-mapping-table-phase1.md

目标：把线上实际运行的老系统（或前一版云试运行）的业务口径、接口形态、表结构抽出来，沉淀为可继承的证据，指导后续 Phase 2/3 的建模与救火。

必做：
1. 从 current-state.md 和 runbook.md 提取：线上 host / 服务名 / 反代路径 / 数据库别名 / 关键 env。若信息缺失，在 docs/deploy/missing-inputs.md 立刻记下并继续（不要卡住其他工作）。
2. 若有只读云端访问：
   a) curl 至少 8 个核心 endpoint 的真实响应（脱敏后存 docs/audits/2026-05-13-cloud-api-shapes/<endpoint-slug>.json）：
      /api/v1/dashboard/factory-director
      /api/v1/dashboard/workshop-director
      /api/v1/reports/daily
      /api/v1/production/summary（若存在）
      /api/v1/mobile/submit（只抓 schema，不实际提交）
      /api/v1/quality/events
      /api/v1/energy/summary
      /api/v1/executive/dashboard
   b) 每个响应写一条"和当前仓库响应 schema 的差异"（对比 backend/app/schemas/ 里对应类型）
3. 继承前轮已知问题：
   a) 读 2026-05-12-live-fill-mes-binding-audit.md，把里面列的"填报→管理端链路"问题点 1:1 搬进本次逆向审计
   b) 读 2026-04-08-legacy-historical-data-gap-review.md，把历史数据缺口整理进同一份审计
4. 产出 docs/audits/2026-05-13-cloud-reverse-audit.md，章节：
   - A. 线上接入点与访问条件
   - B. 8 个核心 endpoint 的真实响应样例（用 <details> 折叠）
   - C. 响应 schema 与当前仓库 schema 的差异（至少 5 条）
   - D. 继承自前轮审计的未解问题（标关联 audit 文件）
   - E. 给 Phase 3 的救火线索（至少 5 条）
   - F. 给 Phase 8 的部署硬性信息缺口（写进 missing-inputs.md）

missing-inputs.md 采用 5 列表格：
| 用途 | 所在文件 | 缺失字段 | 影响范围 | 建议取值 |

硬约束：
- 响应样例必须脱敏（手机号 / 身份证 / 真实姓名 / IP / token 一律替换成 <REDACTED-*>）
- 禁止把生产 token / DB 密码写进任何 md 或 commit
- 响应样例若超过 2KB，截断并在 md 里标 "..."
- 无访问权限时不要假装访问；在 missing-inputs.md 列出所需凭证后停下等人工

交付：
- docs/audits/2026-05-13-cloud-reverse-audit.md
- docs/audits/2026-05-13-cloud-api-shapes/*.json（至少 8 个，若权限不足则生成 placeholder 并在 reverse-audit.md 标出）
- docs/deploy/missing-inputs.md（若有缺口）
- docs/superpowers/audits/2026-05-13-phase-1-5-done.md

验收：
- 8 个 endpoint 样例齐全或在 missing-inputs.md 里标明
- 至少 5 条 schema 差异 + 5 条救火线索

提交：docs(audit): cloud reverse audit + missing-inputs registry
收工前粘贴 git status --porcelain。
```

---

## Phase 2 · 鑫泰真实口径沉淀

**Status:** TODO | **Designed for:** Codex | **Allowed write paths:** `backend/app/domain/**`, `backend/tests/test_calculators.py`, `docs/domain/**`

### 前置依赖

- 无。Round 1 与 Phase 0、Phase 1 并行。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的领域建模员。只许写：
- backend/app/domain/ 下的 Python（新增目录）
- backend/tests/test_calculators.py
- docs/domain/ 下的 md（新增目录）

开工前读：
1. CLAUDE.md / AGENTS.md / DESIGN.md
2. backend/app/models/production.py / energy.py / quality.py / attendance.py / mes.py 的字段定义
3. backend/app/services/daily_production_canonical_service.py 和 daily_energy_report_service.py 的现有公式
4. docs/mes-field-mapping-table-phase1.md
5. docs/import-templates/ 下 4 份样例说明
6. D:\鑫泰报表\5.5\ 和 D:\鑫泰报表\5.4\ 下所有 Excel（只读，不拖进 repo）

目标：把鑫泰真实生产 Excel 里的字段、单位、口径沉淀成代码层的 domain / calculator / unit_conversion，后续 Phase 3/5/7 全部引用它，禁止再散落各处。

必做：
1. 遍历 D:\鑫泰报表 至少 5 天归档（5.1 / 5.2 / 5.3 / 5.4 / 5.5），按模块归类：生产、能耗、质量、考勤、库存、合同、成本。对每类文件，抽取：
   - 字段原名（中文）+ 英文 slug
   - 单位（吨 / 千克 / 千瓦时 / 立方米 / 度 / 小时 / ...）
   - 数值量级（典型值 + 单日最大 + 单日最小）
   - 统计周期（班 / 日 / 周 / 月 / 年）
   - 聚合方式（求和 / 均值 / 最大 / 最小 / 比例 / 差分）
   - 业务口径文字（一句话说清楚"这个数字代表什么"）

2. 产出 docs/domain/xintai-real-fields.md，分 7 个小节（生产 / 能耗 / 质量 / 考勤 / 库存 / 合同 / 成本），每小节一张字段表，每字段一行，附来源文件名和 sheet 名。至少 120 个字段。

3. 产出 backend/app/domain/__init__.py 和 backend/app/domain/calculators/ 目录：
   - production_calculators.py：yield_rate / scrap_rate / shift_output / daily_cumulative_output / monthly_cumulative_output
   - energy_calculators.py：unit_energy_consumption（单位能耗）/ peak_valley_split / cross_workshop_aggregate
   - quality_calculators.py：defect_rate / pareto_top_n / disposition_breakdown
   - attendance_calculators.py：attendance_rate / overtime_hours / makeup_card_rate
   每函数必须：
     a) 纯函数，无副作用，不碰数据库
     b) docstring 写清口径来源（引用 xintai-real-fields.md 的小节）
     c) 参数名用中文拼音 slug（如 tou_liao_liang），避免含糊的 amount
     d) 单位在参数名末尾显式标注（如 tou_liao_liang_kg, chan_liang_ton）

4. 产出 backend/app/domain/unit_conversions.py：
   - MASS_KG_TO_TON = 0.001
   - ENERGY_KWH_TO_MJ = 3.6
   - VOLUME_M3_TO_L = 1000
   - 每常量附来源注释 + "鑫泰口径" 或 "国标" 标签

5. 产出 backend/tests/test_calculators.py：
   对每个 calculator 写至少 3 条断言，数据取自 5.5 的真实 Excel（用 @pytest.mark.parametrize 排列）。禁止写 assert result == result 这种无意义断言。

6. 产出 docs/domain/calibration-log.md：每条口径决策一条 log，格式：
   - 日期 / 决策点 / 候选方案 / 选择 / 理由 / 来源

硬约束：
- 不拖 Excel 原件进 repo
- 不改 backend/app/services / routers / models 的既有文件（本 phase 只新增 domain 层）
- 所有 calculator 禁止 import SQLAlchemy / FastAPI
- 无法确定的字段一律标 TODO 且列入 docs/domain/xintai-real-fields.md 的 "Unresolved" 小节，不许猜
- pytest 必须全绿才能 commit

交付：
- docs/domain/xintai-real-fields.md（≥ 120 字段）
- backend/app/domain/ 目录（至少 4 个 calculator 文件 + unit_conversions.py）
- backend/tests/test_calculators.py（至少 40 条断言）
- docs/domain/calibration-log.md
- docs/superpowers/audits/2026-05-13-phase-2-done.md

验收：
- pytest backend/tests/test_calculators.py 全绿
- xintai-real-fields.md 字段数 ≥ 120
- calibration-log.md 条目 ≥ 20

提交：feat(domain): extract real-world field catalog + calculators + unit conversions from 鑫泰报表
收工前粘贴 git status --porcelain。
```

---

## Phase 3 · 救火：填报→管理端全链路 + 10w 异常溯源

**Status:** TODO | **Designed for:** Codex + Claude 验收 | **Allowed write paths:** `backend/app/services/**`, `backend/app/routers/**`, `backend/tests/**`, `scripts/clean_*.py`, `docs/superpowers/audits/`

### 前置依赖

- Phase 2 已合（需要真实口径做回归断言上限）
- Phase 1.5 已合（继承线索）

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的救火工程师。允许写：
- backend/app/services / backend/app/routers 里已有的文件
- backend/tests/ 新增或修改文件
- scripts/clean_*.py 新增脚本
- docs/superpowers/audits/ 下本轮审计 md

不允许：
- 改 backend/app/models/ 的表结构（救火不改 schema）
- 改 backend/app/domain/（Phase 2 已锁定口径）
- 改前端任何文件（本 phase 专注后端 + 数据）

开工前读：
1. docs/audits/2026-05-12-live-fill-mes-binding-audit.md（前轮已经定位一部分）
2. docs/superpowers/audits/2026-05-13-status-audit.md（Phase 1 产出）
3. docs/superpowers/audits/2026-05-13-cloud-reverse-audit.md（Phase 1.5 产出）
4. docs/domain/xintai-real-fields.md（Phase 2 产出，回归断言的上限）
5. backend/app/services/daily_production_canonical_service.py
6. backend/app/services/app_connection_service.py
7. backend/app/routers/mobile.py / dashboard.py / reports.py

目标：
A) 修复填报端提交后 5 秒内管理端可见
B) 消灭管理端产量 ~10w 的数据异常
C) 打通"填报 → 数据库 → 管理端 KPI → 管理端详情 → 报表中心 → 导出 Excel"的 5 个落点

必做：
1. 先写失败回归测试：
   backend/tests/test_full_chain_visibility.py
   - 构造一条 mobile.submit 请求（用真实字段）
   - 5 秒内（polling）断言在 5 个落点都能查到：
     a) ShiftProductionData 表有对应 row
     b) /api/v1/dashboard/factory-director 返回的 today_kpi 包含此 row
     c) /api/v1/dashboard/workshop-director 同上
     d) /api/v1/reports/daily 日报表里能查到
     e) /api/v1/export/daily 导出的 Excel 第一个 sheet 含此 row
   跑 pytest 让它红，用红灯暴露断链处。

2. 10w 异常溯源：
   - 在 daily_production_canonical_service.py 加临时诊断 logger（完工前删）
   - 用真实测试数据触发 /api/v1/dashboard/factory-director
   - 对比返回的产量 vs Phase 2 calculators 的 daily_cumulative_output 期望值
   - 根因归类（至少排查这 4 类）：
     a) 单位换算错（kg 当 ton 用，倍差 1000）
     b) data_status 过滤错（把 voided / draft 也算进来）
     c) 重复累计（JOIN 爆炸 / 两个 service 各算一遍）
     d) business_date 对齐错（UTC vs Asia/Shanghai 漂了 1 天）

3. 产出 docs/superpowers/audits/2026-05-13-data-chain-rca.md，含：
   - A. 断链点清单（每点附 file:line）
   - B. 10w 异常根因（每个根因附 SQL / service / 日志截图）
   - C. 修复方案清单（每条标影响面 + 预估工时）
   - D. 需要清洗的历史脏数据（行数估算 + 清洗条件）

4. 分 commit 修复，每个根因一个 commit，标题格式 fix(data-chain): <short-reason> (rca-<N>)，body 附 before/after 数字对比

5. 清洗脏数据：
   scripts/clean_bad_production_rows.py 必须支持：
   --dry-run 先打印要删除的行（默认模式）
   --apply 才真删（需显式加）
   --before <date> --after <date> 时间范围
   打印每行的 id / business_date / workshop_id / 怀疑原因
   写成表格输出方便复制给人工

6. 补回归测试：
   backend/tests/test_factory_dashboard_sanity.py
   - 产量总和 ≤ workshops × 日产能上限（上限从 Phase 2 calibration-log.md 取）
   - 单位能耗 ≤ 鑫泰历史最大值 × 1.5
   - 成品率 ∈ [0, 1]
   - 任何负数直接 fail
   - 跨月 rollup 必须等于日累加（误差 < 0.01）

7. 收工前删所有临时 logger，scripts/clean_*.py 留但要求 --apply 显式

硬约束：
- 不得直接 DELETE，一律走 scripts/clean_*.py --dry-run 由人工执行
- 不得 pass / 跳过任何新增测试
- 不得用 try/except 吞错误掩盖问题

交付：
- docs/superpowers/audits/2026-05-13-data-chain-rca.md
- 修复 commits（每根因一条）
- scripts/clean_bad_production_rows.py
- backend/tests/test_full_chain_visibility.py（全绿）
- backend/tests/test_factory_dashboard_sanity.py（全绿）
- docs/superpowers/audits/2026-05-13-phase-3-done.md

验收：
- 新 mobile.submit 数据 5 秒内出现在 5 个落点
- /dashboard 返回值与 Phase 2 期望值误差 < 1%
- test_full_chain_visibility.py + test_factory_dashboard_sanity.py 全绿

提交节奏：每个根因一个 commit，最后一条 test(chain): add full-chain visibility + sanity bound regression
收工前粘贴 git status --porcelain。
```

---

## Phase 4 · 设计系统组件库沉淀

**Status:** TODO | **Designed for:** Gemini | **Allowed write paths:** `frontend/src/components/xt-{layout,data,chart,form}/**`, `frontend/src/composables/**`（新增，不改既有 useHudTheme.js）, `frontend/tests/**`

### 前置依赖

- Phase 0（GAP_MATRIX）+ Phase 3（数据可信）完成。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的前端基础设施工程师。只许写 frontend/src/components/xt-* 下新组件、frontend/src/composables 下新 composable、frontend/tests 下新测试。严禁改 frontend/src/views/、frontend/src/layout/ManageShell.vue、frontend/src/views/Login.vue、frontend/src/design/。

开工前读：
1. DESIGN.md
2. docs/ui-reference/GAP_MATRIX.md（Phase 0 产出）
3. docs/ui-reference/UI_TARGET_SPEC.md
4. frontend/src/design/xt-hud.css + echarts-hud.js
5. frontend/src/composables/useHudTheme.js
6. frontend/src/components/ 当前清单（避免重名）

目标：在已有 HUD 地基上沉淀可复用的 xt-* 前缀组件库，让 Phase 5/6/7 像拼乐高。

必做（每组件至少 3 条 node test）：

xt-layout：
- XtAppShell.vue（四槽：left / top / main / drawer）
- XtDashboardGrid.vue（props cols: 12|16，断点塌陷）
- XtKpiRibbon.vue（props items: KpiItem[]）
- XtSectionCard.vue（props title, actions slot, empty slot, loading prop）
- XtCommandBar.vue（日期 + 范围 + 过滤 + 导出）
- XtDrawer.vue（右 420px，persistent prop）

xt-data：
- XtMetricCard.vue（value / unit / delta / deltaMode / trend slot / status）
  tabular-nums 必需；delta>0 绿↑ / <0 红↓ / abs<0.1% 灰→
- XtDataTable.vue（el-table wrapper，内置 loading / empty / page / sort）
- XtEmptyState.vue（icon / title / description / action slot）
- XtLoadingSkeleton.vue（rows: number=3）
- XtErrorPanel.vue（error / retry）

xt-chart（固定 theme="xt-hud"，grid{top:32,right:16,bottom:48,left:48,containLabel:true}，connectNulls:false）：
- XtLineChart.vue
- XtBarChart.vue
- XtGaugeChart.vue
- XtTrendSpark.vue（120×32，无坐标轴，给 XtMetricCard 用）

xt-form：
- XtDateRangePicker.vue（快捷 今日/昨日/本周/本月/本季/本年/近7天/近30天）
- XtNumericInput.vue（suffix 单位 + tabular-nums）
- XtUnitSelect.vue
- XtShiftPicker.vue

composables（新增，不改 useHudTheme.js）：
- useDateRange.js（XtDateRangePicker v-model ↔ URL query 同步）
- useTableQuery.js（XtDataTable page/sort/filter ↔ URL query）
- useMetricCompare.js（封装 /<module>/comparison?mode=yoy|mom|wow）

frontend/src/components/README.md：每组件一行 + 用法一句 + 对应 highres 图号。

硬约束：
- 不引入新依赖
- 不写 inline 色值，全走 CSS 变量（--xt-hud-* / --xt-*）
- 所有数字 tabular-nums
- props 必须 JSDoc + 单位
- 组件 name Xt 前缀，kebab-case 文件名
- 测试用 @vue/test-utils + jsdom，不起浏览器

交付：
- ≥ 18 个 .vue
- 3 个 composable
- 对应 test 文件
- components/README.md
- docs/superpowers/audits/2026-05-13-phase-4-done.md

验收：
- cd frontend && npm run test 全绿
- cd frontend && npm run build 成功；主 chunk 增量 ≤ 30 KB gzip
- scripts/hud-guardrails.ps1 全绿

提交：feat(ui): seed xt-layout / xt-data / xt-chart / xt-form component library + composables
收工前粘贴 git status --porcelain。
```

---

## Phase 5 · 管理端三大驾驶舱

**Status:** TODO | **Designed for:** Gemini | **Allowed write paths:** `frontend/src/views/dashboard/**`, `frontend/src/views/factory-command/**`, `frontend/src/views/executive/**`, `frontend/e2e/dashboard-*.spec.js`, `backend/app/services/**`（仅补聚合 service）, `backend/app/routers/dashboard.py`（只追加 endpoint，不改既有）, `backend/app/schemas/**`（新增）, `backend/tests/**`

### 前置依赖

- Phase 2（calculator）+ Phase 3（数据可信）+ Phase 4（组件库）全部完成。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的管理端驾驶舱工程师。只许写上述 Allowed write paths 下文件。严禁改 backend/app/models/、frontend/src/layout/、frontend/src/design/、frontend/src/views/Login.vue。

开工前读：
1. docs/ui-reference/GAP_MATRIX.md
2. docs/ui-reference/highres/01-overview.png / 05-factory-board.png / executive 对应图
3. docs/ui-reference/UI_TARGET_SPEC.md 对应小节
4. frontend/src/components/README.md（Phase 4 组件清单）
5. backend/app/domain/calculators/ 全部（Phase 2）
6. backend/app/services/report_service.py / ai_briefing_service.py 等现有 service

目标：三页视觉达到参考图质感；所有 KPI 走真实 endpoint + calculator 口径；支持日/周/月/YTD tab 切换、同环比、点击下钻抽屉。

必做：

/manage/overview 全域生产中枢总览：
- 顶部 XtKpiRibbon 6 KPI（当日产量 / 合格率 / 能耗 / 异常事件 / 订单履约 / 库存周转）
- 每卡支持 日/周/月/YTD tab（/api/v1/<module>/cumulative?scope=...）
- 每卡同环比小行（/api/v1/<module>/comparison?mode=yoy）
- 中左：工厂地图热力（按车间 output_weight 占比 #04101f→#5eb8ff）
- 中右：AI 摘要卡（/api/v1/ai/briefing/today；AI 未配置显示"AI 未开启"真实占位，禁止假文本）
- 底：事件时间线（/api/v1/notifications?type=critical）

/manage/factory 工厂总览：
- 顶 XtKpiRibbon（车间级）
- 中 车间矩阵卡（每卡：OEE 仪表 + 合格率 spark + 班次进度）
- 底 质量事件散点（x=时间 y=车间 size=严重度）

/manage/executive 经营驾驶舱：
- 顶 4 KPI（收入 / 成本 / 利润 / 毛利率）
- 中左 利润瀑布（收入→原料→能耗→人工→其他→利润）
- 中右 近 12 月同比趋势
- 底左 合同交付进度（水平 bar）
- 底右 成本构成饼

每页都：
- URL query 同步（?date=... &scope=... &cum=month）
- 顶部 XtCommandBar 统一过滤
- KPI 卡 click → XtDrawer 打开，抽屉内嵌 XtLineChart timeseries（/api/v1/<module>/timeseries）
- 空态 XtEmptyState / loading XtLoadingSkeleton / 错误 XtErrorPanel

后端补全（若缺失）：
- GET /api/v1/<module>/cumulative?scope=daily|weekly|monthly|ytd
- GET /api/v1/<module>/comparison?mode=yoy|mom|wow&anchor=<date>
- GET /api/v1/<module>/timeseries?metric=...&date_from=...&date_to=...&granularity=hour|shift|day|week|month
一律 Phase 2 calculator 聚合，router 不写公式；date_to-date_from ≤ 90 天限制；空期间 200 + 空数组。

e2e：
- frontend/e2e/dashboard-overview.spec.js / dashboard-factory.spec.js / dashboard-executive.spec.js
- 每份覆盖：首屏 / tab 切换 / 抽屉 / 空态 / URL query 回显

硬约束：
- 禁止假数据；接口缺失先补后端
- 禁止 SaaS 三卡 / 紫蓝渐变 / emoji
- 不得在 .vue 里写公式
- 新增前端代码 gzip 增量 ≤ 80 KB 每页
- 所有数字 tooltip 必须写"数据来自 XXX / 口径 XXX / 刷新于 HH:mm"

交付：
- 三页 + 对应后端 endpoint + e2e
- docs/superpowers/audits/2026-05-13-phase-5-done.md

验收：
- pytest / npm run test 全绿
- e2e 三页全绿
- 人工截图对比参考图近似度 ≥ 80%
- scripts/hud-guardrails.ps1 全绿

提交：
- feat(manage): overview command center dashboard
- feat(manage): factory-command workshop matrix dashboard
- feat(manage): executive profitability dashboard
收工前粘贴 git status --porcelain。
```

---

## Phase 6 · 移动录入 + 审核链路

**Status:** TODO | **Designed for:** Gemini | **Allowed write paths:** `frontend/src/views/mobile/**`, `frontend/src/views/entry/**`, `frontend/src/views/review/**`, `frontend/e2e/mobile-*.spec.js`, `frontend/e2e/review-*.spec.js`, `backend/app/routers/mobile.py`（仅追加）, `backend/app/services/audit_service.py`（修改 OK）, `backend/app/models/` 新建 AuditTrail 若缺失, `backend/tests/**`

### 前置依赖

- Phase 3（数据链路已修）+ Phase 4（xt-form 组件就位）。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的移动端 + 审核链路工程师。只许写上述 Allowed write paths 下文件。

开工前读：
1. docs/ui-reference/highres/03-entry-home.png / 04-entry-flow.png / 07-review-tasks.png
2. docs/ui-reference/UI_TARGET_SPEC.md 移动端 + 审核端小节
3. frontend/src/views/mobile/ / entry/ / review/ 现有文件
4. backend/app/routers/mobile.py / backend/app/services/audit_service.py
5. backend/app/domain/calculators/production.py（计算口径）

目标：一线工人钉钉 H5 填报顺手；审核员桌面完整追溯；全链路可审。

必做：

/entry 首页：
- 按角色展示今日待填报任务卡 + 草稿箱入口 + 历史记录入口
- 任务卡显示：车间 / 班次 / 截止时间 / 状态（未开始 / 草稿 / 已提交 / 已审核 / 已打回）

/entry/shift-report 班报：
- 按卷录入（产品卷号 / 投料重量 / 产出重量 / 合格重量 / 废品重量）
- 自动计算（合格率 = 合格/投料，调 Phase 2 calculator.calculate_qualified_rate，前端仅展示，计算仍在后端 submit 时统一）
- 强校验：
  - 数量 > 0
  - 合格 ≤ 产出 ≤ 投料
  - 单位 enum（吨/千克，默认吨）
  - 同日同班同卷号去重提交拦截（前后端双校验）
- 异常补录入口（挂异常原因 + 证据照片上传）
- 草稿自动保存到 IndexedDB（每 3 秒），云端持久化走 POST /api/v1/mobile/draft（若不存在则新增）
- 断网：草稿仍可写 IndexedDB；恢复网络提示"有 X 份本地草稿可上传"

/entry/history：
- 查 30 天内自己填报的全部记录，点击进入只读详情 + 审核状态 + 打回原因

/manage/review（或 /manage/audit）：
- 待审核任务队列（按车间 / 日期筛选 XtDataTable）
- 点击 → XtDrawer：展示填报明细 + 原始照片（若 mobile 上传）+ 审核意见输入 + 批准/打回带原因
- 审核打回必须带原因（前端校验 ≥ 5 字符）
- 审核批准 → 调 /api/v1/review/approve/<id>，该条数据 data_status 改 approved，dashboard 立即可见

AuditTrail 模型（若不存在则新建 backend/app/models/audit_trail.py）：
- id / entity_type / entity_id / user_id / action / from_state / to_state / note / ts
- submit / draft_save / auto_calc / approve / reject / revise 全记录
- GET /api/v1/audit/trail/<entity_type>/<entity_id> 返回链路

e2e 全链路：
- frontend/e2e/mobile-shift-report.spec.js
- frontend/e2e/review-approve.spec.js
- frontend/e2e/mobile-offline-draft.spec.js
- 场景：submit → 管理端队列出现 → 批准 → 看板刷新（调用 dashboard endpoint 断言新数据）

硬约束：
- 移动所有点击区 ≥ 44 px
- 数字输入必须 inputMode="numeric"
- 草稿必须本地 + 云端双写
- 打回必须带 ≥ 5 字符原因
- 禁止绕过强校验提交脏数据
- 所有审核动作写 AuditTrail，不得绕开

交付：
- /entry 三页 + /manage/review 一页
- AuditTrail 模型 + API
- e2e 三份
- docs/superpowers/audits/2026-05-13-phase-6-done.md

验收：
- pytest / npm run test / e2e 全绿
- 模拟一条班报从填报→看板 < 10 秒
- 打回重填流程跑通
- 离线草稿恢复跑通

提交：
- feat(mobile): shift-report workflow with draft + validation
- feat(audit): audit trail + review approve/reject + visibility chain
- test(e2e): mobile + review full chain coverage
收工前粘贴 git status --porcelain。
```

---

## Phase 7 · 其他业务模块批量填充（三批串行）

**Status:** TODO | **Designed for:** Gemini + Codex | **Allowed write paths:** 按批划分（见下）

### 前置依赖

- Phase 2（calculator）+ Phase 4（组件库）+ Phase 5（驾驶舱样板）+ Phase 6（移动+审核）完成。

### Codex Prompt（总纲，三批各自跑一轮）

```
你是鑫泰铝业数据中枢项目的业务模块批量交付工程师。按批执行，不跨批。

开工前读（每批都要）：
1. docs/ui-reference/GAP_MATRIX.md 对应批次行
2. docs/ui-reference/highres/ 对应图号
3. frontend/src/components/README.md
4. backend/app/domain/calculators/ 对应模块

通用必做（每页都）：
- 三段式：顶 XtKpiRibbon / 中 趋势 / 底 明细表
- 空态 / 异常态 / loading 态齐全
- 每页 ≥ 2 条 e2e
- 所有图表 theme="xt-hud"
- AI 类页面禁止假文本；env 未配置时返回"AI 未开启"真实占位

---

批 1：生产闭环（Allowed write paths: frontend/src/views/{quality,energy,inventory}/**, backend/app/services/**, backend/app/schemas/**, backend/tests/**, frontend/e2e/**）

- /manage/quality 质量异常：事件时间线 / 不合格率趋势（spark）/ 八大缺陷 Pareto / 单批次下钻
- /manage/inventory 库存出入库：实时库位 / 进出明细 XtDataTable / 异动告警卡
- /manage/energy 能耗产量：单位能耗趋势 / 峰谷分布 / 产能匹配度 / 按车间分组

验收：3 页 / 3 × 2 e2e / 单元 + 集成测试全绿
提交：
- feat(manage): quality exception center
- feat(manage): inventory in-out center
- feat(manage): energy-output efficiency center

---

批 2：经营闭环（Allowed write paths: frontend/src/views/{cost,contracts}/**, backend/app/services/**, backend/app/schemas/**, backend/tests/**, frontend/e2e/**）

- /manage/cost 成本与效益：BOM 成本构成 / 单吨成本走势 / 毛利热力
- /manage/contracts 合同与订单：履约进度 水平 bar / 延期预警 / 客户排行 XtDataTable

验收：2 页 / 2 × 2 e2e
提交：
- feat(manage): cost-efficiency center
- feat(manage): contracts-orders center

---

批 3：系统 + AI（Allowed write paths: frontend/src/views/{ops,admin,settings,ai}/**, backend/app/services/ai_*, backend/app/routers/ai.py（追加）, backend/tests/**, frontend/e2e/**）

- /manage/ops 运维告警：设备 MTBF/MTTR / 告警分级 / 工单关联
- /manage/admin 权限组织：RBAC 树 / 审计日志（调 AuditTrail）
- /manage/settings 系统配置：参数 / 口径 / 班次 / 产品
- /manage/ai AI 中枢：
  - 摘要（今日 5 条，调 /api/v1/ai/briefing/today）
  - 洞察（周级归因，调 /api/v1/ai/insights/weekly）
  - 预警（阈值 + 自动触发，调 /api/v1/ai/warnings/active）
  - 决策建议（卡片 [采纳] [忽略] [改日再议]，采纳 → 生成工单（写 work_orders 表）+ 写 AuditTrail，留全链路审计）

AI 闭环硬约束：
- 禁止写死假文本
- env 未配置时返回"AI 未开启"真实占位
- 建议采纳后必须 1) 生成工单 2) 写 AuditTrail，禁止只改前端状态
- 所有 AI 生成文本前端打标签"AI 生成，人工复核"

验收：4 页 / 4 × 2 e2e / AI 闭环 e2e（采纳 → 工单 → trail 可查）
提交：
- feat(manage): ops alerting + work-order linkage
- feat(manage): admin RBAC tree + audit log
- feat(manage): settings parameter center
- feat(manage): ai hub with briefing / insights / warnings / decisions (full audit trail)

---

每批收工前粘贴 git status --porcelain 和 git log --oneline -5。
每批 Done 后写 docs/superpowers/audits/2026-05-13-phase-7-batch-<N>-done.md。
```

---

## Phase 8 · 联调 / 视觉精修 / 部署收口

**Status:** TODO | **Designed for:** Claude | **Allowed write paths:** `docs/deploy/**`, `docs/superpowers/audits/**`, `scripts/**`, 极个别精修时碰 `frontend/src/components/**` 或 `frontend/src/views/**`

### 前置依赖

- Phase 5/6/7 全部完成。

### Codex Prompt

```
你是鑫泰铝业数据中枢项目的发布工程师。只许写 docs/deploy/、docs/superpowers/audits/、scripts/ 下文件；精修视觉可改 frontend/src/views 或 components 的对应文件（但每次改必须先在 GAP_MATRIX.md 里标 gap，不许漫无边际）。

开工前读：
1. docs/ui-reference/GAP_MATRIX.md（所有 Phase 5/6/7 结束时的最新状态）
2. docs/ui-reference/highres/ 全部
3. docs/superpowers/audits/2026-05-13-phase-{0..7}-done.md
4. docs/deploy/current-state.md / runbook.md
5. docs/deploy/missing-inputs.md（Phase 1.5 产出）

目标：上线级交付。每页视觉 ≥ 参考图 90%；性能达标；部署清单完整；缺口清单精准。

必做：

1. 视觉精修：
   - 逐页与 highres 截图对比
   - 偏差 > 10% 的页面在 GAP_MATRIX.md 加红色"收口中"标记
   - 精修到偏差 ≤ 10%（色差、间距、字号、对齐）
   - 每次精修必须用 /design-review 跑一次 baseline 对比

2. 性能预算：
   - LCP < 2 s（管理端首屏）
   - 移动端 TTI < 3 s
   - 主路由 chunk ≤ 300 KB gzip
   - vendor-three 独立（Phase 1 已验证）
   - 跑 npm run build --report，截图贴到 docs/deploy/perf-report-2026-05-13.md

3. 闸门全量跑绿：
   - scripts/hud-guardrails.ps1 全绿
   - pytest 全绿
   - npm run test 全绿
   - e2e 全绿
   - /design-review 逐页出分，baseline 存 ~/.gstack/projects/xintai/designs/

4. 部署清单 docs/deploy/2026-05-13-go-live.md：
   - 环境变量表（用途 / 所在文件 / 缺失影响）
   - docker-compose.prod.yml 差异点
   - alembic 迁移顺序（特别是 0028_user_preferences 之后新增的）
   - 数据清洗脚本执行节奏（生产 / 测试先后）
   - 回滚手册（每 PR 一条 revert 指令）

5. 缺失信息清单 docs/deploy/missing-inputs-final.md：
   - 合并 Phase 1.5 产出 + Phase 8 发现
   - 必须列 5 列：用途 / 所在文件 / 缺失字段 / 影响范围 / 建议取值
   - 列完立即停下等人工
   - 严禁写假值塞进 .env 绕过

6. 首次部署脚本 scripts/first-deploy-prep.sh / .ps1：
   - 检查 .env 齐全
   - 跑 alembic upgrade head
   - 跑 seed（若存在）
   - 跑全量测试
   - 跑 build
   - 生成 deploy manifest 到 docs/deploy/manifests/<date>.json

硬约束：
- 禁止 force push / --no-verify
- 生产库只读操作外一律写 script + --dry-run 再执行
- 收到 missing-inputs 必须一次性列完再停，不许挤牙膏

交付：
- GAP_MATRIX.md 最终版（所有页达标）
- docs/deploy/go-live + perf-report + missing-inputs-final
- scripts/first-deploy-prep.*
- docs/superpowers/audits/2026-05-13-phase-8-done.md

验收：
- 任何工程师拿到 go-live 文档能独立完成试运行
- 所有闸门全绿
- 视觉偏差全站 ≤ 10%

提交：
- chore(release): visual polish convergence
- chore(release): go-live prep + perf report + missing inputs
- chore(release): first-deploy-prep scripts
收工前粘贴 git status --porcelain 和 git log --oneline -20。
```

---

## 使用建议

**开跑的最小必须顺序：**

1. Round 1（并行）：开 3 个终端分别跑 Phase 0 / Phase 1 + 1.5 / Phase 2
2. Round 1 全部 done 后合并一次
3. Round 2：Phase 3（独占，必须单跑）
4. Round 3：Phase 4（独占）
5. Round 4（并行）：Phase 5 / Phase 6 / Phase 7 批 1
6. Phase 7 批 2、批 3 可在 Round 4 部分完成后加开
7. Round 5：Phase 8（独占）

**每 Round 之间的人工检查点：**

- `git log --oneline <round-start>..HEAD` 看 commit 是否在各自 Allowed write paths 内
- `git status --porcelain` 看是否有越界
- 读本 Round 各 phase 的 done.md 是否该交付都交了
- 跑一次 `./scripts/hud-guardrails.ps1`

**Codex 在一轮卡住（≥ 3 次失败）的应对：**

1. 让 Codex 停下，把 done.md 写成 BLOCKED 状态
2. 人工读 Codex 最近 3 次输出，找卡点
3. 把卡点写回本 plan 的对应 Phase 作为"已知坑"，然后重启该 Phase（不重跑其他）

**本 plan 自身不是不可变的：**

- 任何 phase 发现 plan 本身错了（路径不存在 / 口径对不上 / 依赖图错），当场改本 plan 对应段落，再 commit 一次 `docs(plan): fix phase-X instruction`，然后继续
- 禁止偷改 prompt 却不更新 plan



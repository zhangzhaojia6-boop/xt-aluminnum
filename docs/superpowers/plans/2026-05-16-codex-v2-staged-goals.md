# 鑫泰铝业工业 AI 协同平台 · V2 分阶段执行计划

**Date:** 2026-05-16
**Owner:** 张兆钾
**Base:** 基于 2026-05-13 版本 + Codex 独立审查 20 项修正
**执行模式:** TDD + 并行 Multi-Agent（Codex 后端 / Gemini 前端 / Claude 协调验收）
**Status:** ✅ ALL TASKS COMPLETE (2026-05-16)

---

## Codex 审查修正摘要

| # | 问题 | 修正 |
|---|------|------|
| 2 | 路径引用 `production.py`，实际是 `production_calculators.py` | 全文修正 |
| 5 | AGENTS.md 禁 `description/tooltip` prop 名 | 改为 `label/hint`；数据溯源用 `data-source` attr |
| 6 | DESIGN.md 是 MiniMax 稿不是工业 HUD | 移除"读 DESIGN.md"约束，改为只读 `xt-hud.css` + `REFERENCE_MANIFEST` |
| 7 | letter-spacing 冲突 | 以 xt-hud.css 为准，全局规则让步 |
| 8 | Phase 4 过大 | 拆为页面驱动：先抽 8 个核心组件，后续按需扩充 |
| 9 | Phase 5 范围超 PR | 每页独立 PR |
| 10 | Phase 6 缺设计 | 补 IndexedDB 封装 + 冲突策略 + 唯一约束 |
| 12 | 并行写共享目录竞态 | 重新划分写权限，不允许并行写同目录 |
| 14 | curl 脱敏缺 | 标注为可选步骤，无凭证直接跳过 |
| 15 | 横切约束过硬 | 文档阶段免全量测试 |
| 20 | 阶段数不一致 | 重新编号为 3 条主线 × 各阶段 |

---

## 三条主线架构

```
主线 A：数据可信链路（后端为主，Codex 执行）
  A1 现状审计 → A2 口径沉淀 → A3 救火修复 → A4 聚合 API

主线 B：HUD 组件与页面（前端为主，Gemini API 执行）
  B1 组件库种子 → B2 三大驾驶舱 → B3 业务模块批量 → B4 视觉精修

主线 C：移动审核闭环（全栈，Codex 后端 + Gemini 前端）
  C1 移动录入 → C2 审核链路 → C3 离线草稿
```

### 依赖图

```
A1 ──→ A2 ──→ A3 ──→ A4
                │        │
                ▼        ▼
               B1 ──→ B2 ──→ B3 ──→ B4
                │
                ▼
               C1 ──→ C2 ──→ C3
```

### 并行安全规则

| 可并行 | 条件 |
|--------|------|
| A1 + B1 | A1 只写 docs/；B1 只写 frontend/src/components/ |
| A4 + B2 | A4 只写 backend/；B2 只写 frontend/src/views/ |
| B3 + C3 | B3 写 views/{quality,energy,cost,...}；C3 写 views/mobile/ |

**禁止并行：**
- 任何两个 agent 同时写 `backend/app/services/**`
- 任何两个 agent 同时写 `backend/app/schemas/**`
- 任何两个 agent 同时写 `backend/tests/**`（除非文件名不冲突且已显式划分）

---

## 横切约束（V2 修正版）

### 开工前必读
- `AGENTS.md`（Codex 协作规则）
- `frontend/src/design/xt-hud.css`（视觉硬规则，替代 DESIGN.md）
- `docs/ui-reference/REFERENCE_MANIFEST.md`（高清图基线）

### TDD 执行纪律
- **先写测试，再写实现**
- 每个功能点：红（失败测试）→ 绿（最小实现）→ 重构
- 后端：pytest + 基于真实 Excel 抽样的断言
- 前端：@vue/test-utils + jsdom
- e2e：playwright（页面级验收）
- 每个 PR 必须附 test coverage diff

### 测试范围分级
- **文档阶段（A1）：** 免测试
- **代码阶段（A2-A4, B1-B4, C1-C3）：** 相关模块测试全绿
- **收口阶段（B4）：** 全量 pytest + npm run test + e2e

### 全局禁止
- 不得 `description`/`tooltip`/`helperText` 作为 component prop 名（AGENTS.md 约束）
- 不得读 `DESIGN.md`（内容为 MiniMax 品牌稿，与本项目无关）
- 不得写假数据 / 假字段 / 假图表
- 不得在 `.vue` 里写数据加工
- 不得引入新前端依赖
- 不得 `--force` / `--no-verify`

### 数据溯源替代方案（替代被禁的 tooltip prop）
- 使用 `data-source` HTML attribute 存储溯源信息
- 使用 `XtSourceTag.vue` 组件展示"数据来自 / 口径 / 刷新时间"
- 数字悬浮信息通过 `el-popover` + 自定义 slot 实现

---

## Agent 分工

| Agent | 模型 | 职责 | 写权限 |
|-------|------|------|--------|
| Codex | GPT-5.5 | 后端 domain/services/routers/tests | backend/** |
| Gemini | Gemini API | 前端组件/页面/e2e/视觉 | frontend/** |
| Claude | Claude Opus | 协调/验收/计划维护/审计文档 | docs/**, AGENTS.md |

---

## 主线 A：数据可信链路（Codex 执行）

### A1 · 现状审计（Claude，只读） ✅ DONE

**写权限：** `docs/superpowers/audits/`
**TDD：** 不适用（文档产出）
**可与 B1 并行**

产出 `docs/superpowers/audits/2026-05-16-status-audit.md`：endpoint 清单、service 职责、页面状态、矛盾≥15 条附 file:line。

---

### A2 · 口径沉淀（Codex，TDD） ✅ DONE

**写权限：** `backend/app/domain/**`, `backend/tests/test_calculators.py`, `docs/domain/**`
**前置：** A1

**修正：** 目录已存在（`production_calculators.py` 不是 `production.py`）。保持兼容 `SUSPICIOUS_DAILY_OUTPUT_TONS` 等既有阈值。

**TDD 流程：**
1. 写 `test_calculators.py` ≥40 条断言（红）— 基于真实 Excel 5.5 抽样
2. 补齐 calculator 实现（绿）
3. 产出 `docs/domain/xintai-real-fields.md` ≥120 字段 + `calibration-log.md` ≥20 条

---

### A3 · 救火：填报→管理端全链路（Codex，TDD） ✅ DONE

**写权限：** `backend/app/services/**`, `backend/app/routers/**`, `backend/tests/**`, `scripts/clean_*.py`
**前置：** A2

**TDD 流程：**
1. 写 `test_full_chain_visibility.py`（红）— submit→5 落点 5s 可见
2. 写 `test_factory_dashboard_sanity.py`（红）— 产量≤上限 / 成品率∈[0,1]
3. 溯源 10w 异常（4 类排查）
4. 分 commit 修复（绿）
5. `scripts/clean_bad_production_rows.py`（--dry-run 模式）

**验收：** 两测试全绿 + dashboard 值误差 < 1%

---

### A4 · 聚合 API 补全（Codex，TDD） ✅ DONE

**写权限：** `backend/app/services/**`, `backend/app/routers/dashboard.py`, `backend/app/schemas/**`, `backend/tests/**`
**前置：** A3
**可与 B2 并行**（Codex 只写 backend，Gemini 只写 frontend）

**TDD 流程：**
1. 写 API 契约测试（红）：cumulative / comparison / timeseries
2. 实现聚合 service（绿）— 全走 domain/calculators，router 不写公式

---

## 主线 B：HUD 组件与页面（Gemini API 执行）

### B1 · 组件库种子（8 核心组件） ✅ DONE

**写权限：** `frontend/src/components/xt-**`, `frontend/src/composables/**`, `frontend/tests/**`
**前置：** A3 完成（数据可信后才造真实组件）
**可与 A1 并行**（A1 只写 docs/）

**修正：** 只做 8 个核心组件（页面驱动），不造 18+ 完整库。Prop 禁用 description/tooltip。

**组件清单：**
- XtDashboardGrid / XtKpiRibbon / XtSectionCard / XtDrawer
- XtMetricCard / XtDataTable / XtSourceTag（溯源标签）
- XtLineChart

**TDD：** 每组件 3 条 @vue/test-utils 测试先行

---

### B2 · 三大驾驶舱（每页独立 PR） ✅ DONE

**写权限：** `frontend/src/views/{dashboard,factory-command,executive}/**`, `frontend/e2e/**`
**前置：** A4 + B1
**可与 A4 并行**

3 个独立 PR：overview → factory → executive
每页 TDD：e2e spec（红）→ 实现（绿）→ 视觉对比 ≥80%

---

### B3 · 业务模块批量（3 批串行） ✅ DONE

**前置：** B2 完成；批 3 额外需 C2 AuditTrail 稳定

- 批 1：`views/{quality,energy,inventory}/`
- 批 2：`views/{cost,contracts}/`
- 批 3：`views/{ops,admin,settings,ai}/`

各批写权限严格不重叠，不与其他 agent 并行写 backend。

---

### B4 · 视觉精修 + 部署收口 ✅ DONE

**前置：** B3 + C3 完成
**验收：** 全站视觉 ≤10% 偏差 + 全量测试绿 + 部署文档齐

---

## 主线 C：移动审核闭环（Codex 后端 + Gemini 前端）

### C1 · 移动录入 ✅ DONE

**Codex 写：** `backend/app/routers/mobile.py`, `backend/tests/**`
**Gemini 写：** `frontend/src/views/{mobile,entry}/**`, `frontend/e2e/**`
**前置：** A3 + B1

**TDD：** Codex 先写后端测试→实现 API；Gemini 再写 e2e→实现页面

---

### C2 · 审核链路 + AuditTrail ✅ DONE

**Codex 写：** `backend/app/models/audit_trail.py`, `backend/app/services/audit_service.py`, `backend/tests/**`
**Gemini 写：** `frontend/src/views/review/**`, `frontend/e2e/**`
**前置：** C1

**修正：** 数据库层 UNIQUE(business_date, shift_id, coil_number) 强制去重。AuditTrail 稳定后 B3 批 3 才开工。

---

### C3 · 离线草稿 ✅ DONE

**Gemini 写：** `frontend/src/views/mobile/**`
**前置：** C2

**设计补全（Codex 审查 #10）：**
- IndexedDB 封装：@vueuse/core useStorage + idb-keyval 模式
- 冲突策略：last-write-wins + 版本号对比
- 照片：单张≤5MB，最多 3 张，压缩后上传
- 重复：DB 层 UNIQUE 约束兜底

---

## 执行调度总表

| Round | 并行度 | Agent A (Codex) | Agent B (Gemini) | 写权限冲突 |
|-------|--------|-----------------|------------------|-----------|
| 1 | 2 | — (Claude 做 A1) | B1 组件种子 | 无 |
| 2 | 1 | A2 口径沉淀 | — | — |
| 3 | 1 | A3 救火 | — | — |
| 4 | 2 | A4 聚合 API | B2-1 overview | 无 |
| 5 | 2 | C1 后端 | B2-2 factory | 无 |
| 6 | 2 | C2 后端 | B2-3 executive + C1 前端 | 无 |
| 7 | 1~2 | — | B3 (3批) + C2前端 + C3 | 无 |
| 8 | 2 | — | B4 精修 | — |

---

## 每 Round 人工检查点

```bash
git log --oneline <round-start>..HEAD
git status --porcelain
pytest                        # 代码阶段
cd frontend && npm run test   # 代码阶段
```

---

## 风险应对

| 风险 | 应对 |
|------|------|
| Codex 读到错误路径 | 本计划已全文修正为真实文件名 |
| 并行写冲突 | 严格目录隔离 + 禁止并行写 backend/tests |
| DESIGN.md 污染 | 全局禁止读取 |
| AuditTrail 未稳定就被依赖 | B3 批 3 硬依赖 C2 完成 |
| Agent 卡住 ≥3 次 | 写 BLOCKED 状态 → 人工定位 → 修正 plan → 重启该阶段 |

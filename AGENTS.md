# Aluminum-Bypass Project Instructions

> Single source of truth for Codex in this repo. Keep it under 100 lines.
> Put durable detail in `docs/`; link there instead of pasting large policy blocks here.

## Mission
- Preserve the production data platform's core goal: remove manual relay work, keep workflows automated, and do not reintroduce human approval hops by accident.
- When business semantics are unclear, read project docs first; do not infer workflow changes from partial code context.

## Tech Stack
- Backend: Python 3.11, FastAPI 0.111, SQLAlchemy 2.0, Alembic, PostgreSQL 15
- Frontend: Vue 3.5 (`<script setup>`), Vite 8, Element Plus 2.8, Pinia, Axios
- Infra: Docker Compose, Nginx 1.27 (SSL/HTTP2), GitHub Actions CI
- Testing: pytest (backend), Playwright (E2E)

## Repo Map
- `backend/app/routers/`: thin API controllers
- `backend/app/services/`: business logic
- `backend/app/models/`: SQLAlchemy models
- `backend/app/schemas/`: Pydantic request/response schemas
- `backend/app/core/`: auth, permissions, event bus, workflow dispatcher
- `backend/app/adapters/`: MES, DingTalk, WeCom integrations
- `frontend/src/views/`: page components
- `frontend/src/api/`, `frontend/src/stores/`, `frontend/src/composables/`: client data flow
- `docs/`: business docs, architecture, SOPs

## Non-Negotiable Rules
- Keep the backend layered: router -> service -> model. Routers stay thin.
- Keep all API routes under `/api/v1/`.
- Validate request and response payloads with Pydantic schemas.
- Use Element Plus for UI; do not introduce another UI library without approval.
- Keep UI text in Chinese and code comments in English.
- Treat `Asia/Shanghai` as the default timezone across the stack.
- Preserve three-tier isolation for admin / audit / user flows: see `docs/三端隔离与数据权限说明.md`.
- Respect RBAC in `backend/app/core/permissions.py`.
- Use the async event bus in `backend/app/core/event_bus.py` where domain events belong.
- Do not bypass `backend/app/core/workflow_dispatcher.py` for workflow execution.

## Ask Before Changing
- `docker-compose.prod.yml`
- Auth or JWT logic
- Nginx SSL configuration
- New pip or npm dependencies
- Any config value hard-coded instead of sourced via `.env` and `backend/app/config.py`

## Schema And API Discipline
- Never skip Alembic. Every schema change needs a migration file.
- If an API contract changes, update the matching Pydantic schemas and router tests.
- If a workflow or permission boundary changes, verify the change against the docs before coding.

## Primary Docs
- Business rules: `docs/第十二轮业务说明.md`
- Permissions and isolation: `docs/三端隔离与数据权限说明.md`
- DingTalk integration: `docs/钉钉预集成说明.md`
- Deployment: `docs/部署文档.md`
- Broader AI/skill planning: `docs/longterm-ai-skill-system-spec.md`

## Common Commands
- Backend tests: `docker compose run --rm backend sh -lc "pytest -q"`
- Single backend file: `docker compose run --rm backend sh -lc "pytest tests/test_xxx.py -q"`
- Frontend build: `cd frontend && npm ci && npm run build`
- Frontend dev: `cd frontend && npm run dev`
- E2E: `cd frontend && npx playwright test`
- Full stack up: `docker compose up -d --build`
- Migrate DB: `docker compose exec backend alembic upgrade head`

## Done Criteria
- Run `docker compose run --rm backend sh -lc "pytest -q"` before declaring completion.
- Run `cd frontend && npm run build` for any frontend-affecting change.
- Create and verify Alembic migrations for schema changes.
- Visually verify UI changes in a browser.
# 鑫泰铝业 · 智能生产数据系统

## 项目使命（第一性原理）

消灭旧流程中"层层接力、重复汇总、数据滞后"的人工统计链条。
实现新流程：**岗位直录 → 系统自动校验/汇总/留痕 → 领导直达**。
中间零人工。

旧流程：`50+工人 → 6组专业统计员 → 综合部总统计 → 领导`
新流程：`50+工人 → 企业微信直录 → 多智能体自动处理 → 领导驾驶舱`

IMPORTANT: 这个系统的核心判断标准永远是——**是否消灭了中间的人工环节**。任何需要人工审核、人工确认、人工发布才能让数据到达领导的设计，都是在重建旧流程。

## 系统定位

这是一个**多智能体驱动的生产数据自动化平台**，不是传统 ERP/MES。
"去统计"只是第一步，后续目标是用智能体替代所有重复、无效、低产的流程，实现降本增效。

## 技术架构

### 三层架构

```
┌─────────────────────────────────────────────┐
│  采集层：企业微信（工人唯一入口）              │
│  H5自建应用 + 企业微信Bot + 消息推送          │
│  目标用户：低素质一线工人，极简交互            │
└────────────────────┬────────────────────────┘
                     │ HTTPS / Webhook
┌────────────────────▼────────────────────────┐
│  引擎层：FastAPI + 多智能体引擎               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │校验Agent │ │汇总Agent │ │催报Agent │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │核对Agent │ │报告Agent │ │预警Agent │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  Claude Agent SDK + 规则引擎 + APScheduler   │
│  PostgreSQL 数据存储                         │
└────────────────────┬────────────────────────┘
                     │ 自动推送
┌────────────────────▼────────────────────────┐
│  展示层：领导驾驶舱（轻量Web/企业微信H5）     │
│  自动生成的日报/看板/分析表                   │
│  异常才通知，无异常则静默                     │
└─────────────────────────────────────────────┘
```

### 技术栈

- **后端框架：** FastAPI (Python 3.11+)
- **数据库：** PostgreSQL 15
- **智能体引擎：** Claude Agent SDK (claude-agent-sdk) + 自定义 MCP Tools
- **规则引擎：** 内置 Python 规则引擎（校验规则、自动确认规则、阈值规则）
- **任务调度：** APScheduler（定时生成报告、定时催报、定时核对）
- **工人前端：** 企业微信自建H5应用（Vue 3 + Vite，嵌入企业微信工作台）
- **消息通道：** 企业微信应用消息 API + Webhook Bot
- **领导端：** 轻量 Web 驾驶舱 / 企业微信H5看板
- **容器化：** Docker + Docker Compose
- **ORM：** SQLAlchemy 2.0 + Alembic 迁移

### 核心依赖

```
# 后端核心
fastapi>=0.111.0
sqlalchemy>=2.0.30
alembic>=1.13.1
pydantic>=2.7.1
uvicorn>=0.30.0
psycopg2-binary>=2.9.9
apscheduler>=3.10.4
httpx>=0.27.0

# 智能体
claude-agent-sdk>=0.16.0
anthropic>=0.52.0

# 企业微信
# 使用 httpx 直接调用企业微信 API，不引入额外 SDK

# 数据处理
openpyxl>=3.1.2
pandas>=2.2.2
pytesseract>=0.3.13  # OCR（可选）

# 前端
vue@3 + vite + element-plus（极简，仅用于企业微信H5内嵌页面）
```

## 代码结构

```
aluminum-bypass/
├── CLAUDE.md                    # 本文件
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 环境变量配置
│   │   ├── database.py          # SQLAlchemy 连接
│   │   ├── models/              # 数据模型（保留现有，精简审核状态机）
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── routers/             # API 端点
│   │   │   ├── wecom.py         # 企业微信回调/数据接收
│   │   │   ├── mobile.py        # H5表单数据提交
│   │   │   ├── dashboard.py     # 驾驶舱数据
│   │   │   └── master.py        # 主数据维护（管理员）
│   │   ├── agents/              # ★ 多智能体模块（新增核心）
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Agent 基类与注册
│   │   │   ├── validator.py     # 校验Agent：数据提交后自动校验
│   │   │   ├── aggregator.py    # 汇总Agent：自动汇总生成日报
│   │   │   ├── reminder.py      # 催报Agent：自动催报/升级
│   │   │   ├── reconciler.py    # 核对Agent：自动差异核对
│   │   │   ├── reporter.py      # 报告Agent：自动生成/发布报告
│   │   │   └── alert.py         # 预警Agent：异常预警通知
│   │   ├── rules/               # ★ 规则引擎（新增核心）
│   │   │   ├── __init__.py
│   │   │   ├── validation.py    # 数据校验规则（字段完整性、范围检查）
│   │   │   ├── auto_confirm.py  # 自动确认规则（无异常则直接通过）
│   │   │   └── thresholds.py    # 阈值规则（差异容忍度、预警线）
│   │   ├── services/            # 业务逻辑（精简，去掉人工审核链）
│   │   ├── adapters/            # 外部系统适配器
│   │   │   ├── wecom.py         # 企业微信 API 适配器
│   │   │   └── mes.py           # MES 系统适配器
│   │   ├── core/                # 核心工具
│   │   │   ├── auth.py          # JWT 认证
│   │   │   ├── permissions.py   # 权限（精简为：工人/管理员/系统）
│   │   │   └── event_bus.py     # 事件总线
│   │   └── utils/
│   ├── tests/
│   ├── alembic/
│   └── requirements.txt
├── frontend/                    # 极简前端（企业微信H5内嵌）
│   ├── src/
│   │   ├── views/
│   │   │   ├── WorkerForm.vue   # 工人填报表单（极简，大按钮大字）
│   │   │   ├── Dashboard.vue    # 领导驾驶舱
│   │   │   └── AdminPanel.vue   # 管理员配置（初始化用）
│   │   ├── api/
│   │   └── main.js
│   └── index.html
└── docs/
```

## 智能体设计原则

IMPORTANT: 每个 Agent 必须遵循以下原则：

1. **自主运行**：不依赖人工触发，由事件或定时器驱动
2. **静默成功**：正常情况下不打扰任何人
3. **异常才通知**：只在需要人工介入时才发送消息
4. **可追溯**：所有决策记录审计日志
5. **可配置**：规则和阈值通过配置管理，不硬编码

### 六大智能体

| Agent | 触发方式 | 输入 | 输出 | 替代了谁 |
|-------|---------|------|------|---------|
| **校验Agent** | 数据提交事件 | 工人提交的原始数据 | 通过/拒绝+原因 | 专业统计员的"核对"工作 |
| **汇总Agent** | 定时(每班次结束后) | 所有已确认的班次数据 | 日报JSON+文本 | 综合部总统计的"汇总"工作 |
| **催报Agent** | 定时(班次结束后30min) | 未提交的班次列表 | 企业微信催报消息 | 追报的人 |
| **核对Agent** | 定时(日报生成后) | 多源数据 | 差异报告 | 核对补缺的人 |
| **报告Agent** | 汇总Agent完成后 | 日报数据 | 格式化报告+自动发布 | 最终出表的人 |
| **预警Agent** | 实时监控 | 异常指标 | 领导预警通知 | 无（新增能力） |

### 数据流（新流程实现）

```
工人在企业微信填报
  → 校验Agent 自动校验
    ├─ 全部合格 → 自动确认（status=confirmed），零人工
    └─ 有异常 → 退回工人修改 + 通知管理员
  → 汇总Agent 定时汇总已确认数据
    → 生成日报
  → 报告Agent 自动发布到驾驶舱
    → 领导企业微信收到日报推送
  → 核对Agent 自动核对多源数据
    ├─ 差异在阈值内 → 自动确认
    └─ 差异超阈值 → 通知管理员
```

IMPORTANT: 注意上面的流程——从工人提交到领导看到，中间没有任何"人工点击确认"的步骤。这就是新流程的核心价值。

## 状态机（精简版）

旧状态机：`pending → reviewed → confirmed → published → locked`（5个状态，3个需要人工操作）

新状态机：`draft → submitted → auto_confirmed / flagged → published`（4个状态，0个需要人工操作）

```
draft          工人保存草稿
submitted      工人提交（触发校验Agent）
auto_confirmed 校验Agent自动确认（合格）
flagged        校验Agent标记异常（需人工处理，仅异常情况）
published      报告Agent自动发布到驾驶舱
```

## 企业微信集成方案

### 工人端（H5自建应用）
- 在企业微信工作台添加自建H5应用
- 工人打开即填报，无需额外登录（企业微信身份自动识别）
- 界面极简：大按钮、大字体、最少字段、一屏完成
- 支持拍照上传（OCR可选）

### 消息通道
- **催报消息**：企业微信应用消息 → 推送到工人
- **日报推送**：企业微信应用消息 → 推送到领导
- **异常预警**：企业微信应用消息 → 推送到管理员
- **Webhook Bot**：用于车间群通知

### 身份认证
- 企业微信 JS-SDK `wx.config` + `wx.agentConfig`
- 通过 `userid` 自动匹配系统员工
- 工人无需记忆用户名密码

## 权限模型（精简）

旧模型：admin / manager / reviewer / mobile_user（4种角色，reviewer 是旧流程的产物）

新模型：
- **worker**：填报数据（企业微信H5）
- **admin**：系统配置、异常处理、规则调整
- **system**：智能体自动操作（审计日志标记为 system_agent）

IMPORTANT: 没有 reviewer 角色。审核由 Agent 自动完成。

## 工人前端设计原则

YOU MUST 确保工人前端满足以下要求：
1. **一屏完成**：所有必填字段在一屏内，不滚动
2. **大字大按钮**：最小字体 16px，按钮高度 48px+
3. **零思考**：不需要工人做任何判断或选择，只填数字
4. **自动填充**：当前班次、车间、班组由系统自动识别
5. **容错**：允许保存草稿、允许修改已提交数据
6. **离线**：弱网环境下可保存，恢复后自动提交
7. **中文**：所有界面纯中文，无英文、无技术术语
8. **反馈即时**：提交后 1 秒内给出结果（成功/哪里有问题）

## 保留的现有资产

以下现有代码可以保留并复用：
- `backend/app/models/` — 数据模型（需精简状态机）
- `backend/app/database.py` — 数据库连接
- `backend/app/config.py` — 环境变量管理
- `backend/app/core/auth.py` — JWT 认证（需适配企业微信）
- `backend/app/services/mobile_report_service.py` — 填报逻辑（去掉审核链）
- `backend/app/services/mobile_reminder_service.py` — 催报逻辑（升级为 Agent）
- `backend/app/routers/dashboard.py` — 驾驶舱数据
- `backend/app/models/production.py` — 生产数据模型
- `alembic/` — 数据库迁移
- `docker-compose.yml` — 容器编排

## 需要删除或重写的部分

- `frontend/src/views/` 中除 Dashboard 相关外的所有桌面端管理页面
- `backend/app/core/permissions.py` 中的 reviewer 相关逻辑
- `backend/app/services/production_service.py` 中 `update_shift_data_status()` 的人工审核流程
- `backend/app/services/report_service.py` 中需要人工触发的 `run_daily_pipeline()`
- 整个 reviewer 角色相关的路由和前端页面
- 导航中所有"审核工作台"类的页面

## 开发工作流

- 每次修改后运行 `docker compose up --build` 验证
- 后端变更用 `pytest` 验证
- 前端变更用 `npm run dev` 本地预览
- 数据库变更用 `alembic revision --autogenerate` 生成迁移
- 提交前确保 `docker compose up` 全部服务健康

## 当前阶段：Phase 1 — 去统计

目标：实现"工人填报 → 系统自动处理 → 领导看到数据"的完整链路，中间零人工。

Phase 1 完成标志：
1. 工人在企业微信填报数据后，无需任何人工审核，领导驾驶舱在 5 分钟内显示最新数据
2. 异常数据自动退回工人，附带明确的修改指引
3. 日报在班次结束后自动生成并推送到领导企业微信
4. 催报消息在班次结束后 30 分钟自动发送给未填报工人
Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

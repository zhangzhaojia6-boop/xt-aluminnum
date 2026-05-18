# 鑫泰铝业 数据中枢 — 完全体过渡方案

**Date:** 2026-05-16
**Owner:** 张兆钾 / Claude Opus 验收
**Scope:** 从当前 90% 半成品状态收口为可交付生产的完全体工业 AI 平台

## 当前状态快照

| 维度 | 完成度 | 关键证据 |
|------|--------|----------|
| 前端页面 | 95% | 65+ vue 页面，221 测试全绿，build 2.13s |
| 后端 API | 92% | 32 路由模块，70+ 服务，829 测试通过 |
| 数据模型 | 95% | 17 模型文件覆盖全业务域 |
| 实时推送 | 80% | SSE 已实现，缺 Service Worker |
| AI 助手 | 60% | mock fallback 兜底，LLM 适配器框架在 |
| 钉钉集成 | 40% | DingTalkService placeholder，配置结构在 |
| MES 对接 | 50% | NullMesAdapter 兜底，适配器接口完整 |
| 离线支持 | 40% | IndexedDB useRetryQueue 有，缺 SW |
| 部署 | 70% | Docker + compose 有，缺 CI/CD |
| 定时任务 | 0% | 无 Celery/APScheduler |

---

## 前端 Agent 任务（Claude Opus 亲自执行）

### F1. Service Worker + PWA 离线体验
**目标：** 移动端填报在断网环境下可完整操作，恢复网络后自动同步
**验收：**
- `navigator.serviceWorker.ready` 在移动端页面可用
- 断网状态下 ShiftReportForm 可填写并保存到 IndexedDB
- 恢复网络后 useRetryQueue 自动提交，UI 显示同步状态
- Lighthouse PWA 评分 ≥ 80

**实现要点：**
- 添加 `vite-plugin-pwa`（Workbox GenerateSW 策略）
- 缓存策略：app shell CacheFirst，API NetworkFirst
- 离线 fallback 页面（简洁提示 + 已缓存数据展示）
- manifest.json（图标、主题色、display: standalone）

### F2. 前端错误监控 + 性能埋点
**目标：** 生产环境异常可追溯，关键性能指标可度量
**验收：**
- Vue errorHandler 捕获未处理异常并上报
- 关键路由 LCP/TTI 通过 PerformanceObserver 采集
- 错误上报到 `POST /api/v1/telemetry/errors`
- 性能数据上报到 `POST /api/v1/telemetry/perf`

**实现要点：**
- `src/plugins/errorMonitor.js` — 全局错误捕获
- `src/composables/usePerformance.js` — 路由级性能采集
- 不引入第三方 SDK（Sentry 等），自建轻量方案

### F3. E2E 测试可执行化
**目标：** `npx playwright test` 可在 CI 中运行
**验收：**
- `playwright.config.ts` 配置完成
- 至少 10 个核心 spec 可在 headless 模式下通过
- CI workflow 中集成 Playwright

**实现要点：**
- 安装 `@playwright/test`
- 配置 baseURL 指向 dev server
- 添加 test fixtures（登录态注入）
- 优先覆盖：登录 → 管理端导航 → 移动端填报 → 审批流

### F4. 移动端体验精修
**目标：** 工人在车间环境下高效使用
**验收：**
- 下拉刷新（touch 手势）
- 弱网骨架屏（加载态 ≤ 300ms 显示）
- 扫码摄像头权限引导（首次使用友好提示）
- 大按钮触控区域 ≥ 44px

**实现要点：**
- `usePullRefresh` composable
- 骨架屏组件 `XtSkeleton.vue`
- 摄像头权限检测 + 引导 UI

### F5. 可访问性基线
**目标：** WCAG 2.1 AA 级基线合规
**验收：**
- 所有 modal 有 focus trap
- 图表组件有 aria-label 描述
- 键盘可完成核心流程（登录 → 导航 → 查看数据）
- 颜色对比度 ≥ 4.5:1

---

## 后端 Agent 任务（Codex 执行）

### B1. 钉钉推送完整实现
**目标：** 填报提醒、异常告警、审批通知通过钉钉工作通知送达
**验收：**
- `DingTalkService.send_work_notification(user_id, content)` 真实调用钉钉 API
- access_token 自动刷新（2h 有效期内缓存）
- 消息模板：填报提醒、异常告警、审批通知、日报推送
- 限流保护（20 条/秒/应用）
- 单元测试覆盖 token 刷新 + 发送 + 限流 + 失败重试

**Spec：**
```python
# app/services/dingtalk_service.py
class DingTalkService:
    async def _refresh_access_token(self) -> str: ...
    async def send_work_notification(self, user_id: str, content: dict) -> bool: ...
    async def send_group_message(self, chat_id: str, content: dict) -> bool: ...
    
# 消息模板 app/services/dingtalk_templates.py
def build_fill_reminder(worker_name: str, shift: str, deadline: str) -> dict: ...
def build_anomaly_alert(workshop: str, metric: str, value: float, threshold: float) -> dict: ...
def build_approval_notice(report_id: int, approver: str, action: str) -> dict: ...
```

### B2. MES 真实适配器
**目标：** 与工厂 MES 系统实时数据同步
**验收：**
- `XintaiMesAdapter` 实现所有 `MesAdapter` 抽象方法
- 跟踪卡查询 ≤ 500ms 响应
- 铝卷快照增量同步（cursor-based）
- 完工回写幂等（重复调用不重复记录）
- 集成测试（mock MES HTTP 响应）

**Spec：**
```python
# app/adapters/xintai_mes_adapter.py
class XintaiMesAdapter(MesAdapter):
    def __init__(self, base_url: str, api_key: str): ...
    def get_tracking_card_info(self, card_no: str) -> CardInfo | None: ...
    def list_coil_snapshots(self, *, cursor=None, updated_after=None, limit=200) -> tuple[list, str|None]: ...
    def get_daily_schedule(self, business_date: date, workshop: str) -> list[ScheduleItem]: ...
    def push_completion(self, card_no: str, output_weight: float|None, yield_rate: float|None) -> bool: ...
```

**前置条件：** 需要 MES 系统 API 文档和测试环境凭据

### B3. 定时任务引擎
**目标：** 周期性业务逻辑自动执行
**验收：**
- APScheduler 集成到 FastAPI lifespan
- 任务列表：
  - 每日 06:00 生成前日班次报表
  - 每 30min 同步 MES 铝卷快照
  - 每日 08:00/14:00/20:00 发送未填报提醒
  - 每周日 02:00 归档 30 天前历史数据
- 任务执行日志持久化
- 失败自动重试（最多 3 次，指数退避）

**Spec：**
```python
# app/core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# app/tasks/daily_report.py
async def generate_daily_reports(business_date: date): ...

# app/tasks/mes_sync.py
async def sync_mes_coil_snapshots(): ...

# app/tasks/fill_reminder.py
async def send_fill_reminders(): ...

# app/tasks/data_archive.py
async def archive_old_data(days_before: int = 30): ...
```

### B4. 数据库迁移正规化
**目标：** `alembic upgrade head` 可从空库建出完整 schema
**验收：**
- 删除 placeholder `001_initial_migration.py`
- 生成真实迁移链（autogenerate from models）
- `alembic downgrade -1` 可回滚最近一次迁移
- seed 脚本 `scripts/seed_production.py` 可初始化基础数据
- CI 中验证迁移链完整性

**Spec：**
```bash
# 生成迁移
alembic revision --autogenerate -m "initial_schema"
# 验证
alembic upgrade head
alembic downgrade base
alembic upgrade head  # 二次升级无报错
```

### B5. AI 助手接入真实 LLM
**目标：** AI 助手从 mock 切换到真实 LLM 响应
**验收：**
- 配置 `LLM_API_BASE` + `LLM_API_KEY` 后，助手返回真实 LLM 回答
- mock fallback 仅在 LLM 不可用时触发
- system prompt 包含工厂上下文（车间、设备、产品、指标）
- token 用量记录到 `assistant_usage` 表
- 单次对话 token 上限 4096（防止成本失控）

**Spec：**
```python
# app/adapters/llm.py — 已有框架，需要：
# 1. 确保 _call_llm_chat() 正确处理 streaming
# 2. 添加 usage tracking
# 3. 添加 cost control (max_tokens, rate limit per user)

# app/services/assistant_service.py — 修改：
# 1. query_assistant() 优先走 LLM，失败才 fallback mock
# 2. daily_briefing() 用 LLM 生成自然语言摘要
```

### B6. 监控 + 遥测端点
**目标：** 生产环境可观测
**验收：**
- `GET /health` 返回 DB 连接状态 + 服务版本
- `GET /metrics` 返回 Prometheus 格式指标
- `POST /api/v1/telemetry/errors` 接收前端错误
- `POST /api/v1/telemetry/perf` 接收前端性能数据
- 结构化 JSON 日志（替代 print）

**Spec：**
```python
# app/routers/health.py
@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> dict: ...

# app/routers/telemetry.py
@router.post("/api/v1/telemetry/errors")
async def receive_frontend_error(payload: ErrorReport): ...

@router.post("/api/v1/telemetry/perf")
async def receive_frontend_perf(payload: PerfReport): ...
```

### B7. 安全加固
**目标：** 生产环境安全基线
**验收：**
- CORS 生产环境只允许 `*.xintai-alu.com`
- JWT refresh token 机制（access 15min + refresh 7d）
- 全局 rate limit（100 req/min/IP）
- 文件上传：类型白名单 + 大小限制 10MB
- 敏感操作审计（用户管理、配置变更、数据删除）

### B8. CI/CD Pipeline
**目标：** 代码提交到部署全自动化
**验收：**
- `.github/workflows/ci.yml`：lint + test + build
- `.github/workflows/deploy-staging.yml`：自动部署测试环境
- `.github/workflows/deploy-prod.yml`：手动触发 + 审批
- Docker 镜像自动构建推送

---

## 执行编排

```
Phase A（上线阻塞，并行执行）
├── 前端: F1 (PWA) + F3 (E2E)
└── 后端: B1 (钉钉) + B4 (迁移) + B7 (安全)

Phase B（核心体验，Phase A 完成后）
├── 前端: F2 (监控) + F4 (移动端精修)
└── 后端: B3 (定时任务) + B6 (监控端点)

Phase C（增值功能，Phase B 完成后）
├── 前端: F5 (可访问性)
└── 后端: B2 (MES) + B5 (AI 助手) + B8 (CI/CD)
```

### 依赖关系

```
B4 (迁移) ──→ B3 (定时任务) ──→ B1 (钉钉提醒调度)
                              ──→ B2 (MES 同步调度)
B6 (监控端点) ←── F2 (前端监控)
B7 (安全) ──→ B8 (CI/CD)
F1 (PWA) ←── F4 (移动端精修，依赖离线能力)
```

### Agent 分工原则

| 角色 | 负责 | 不做 |
|------|------|------|
| Claude Opus（前端） | F1-F5，视觉品质，交互设计，组件 API | 后端逻辑 |
| Codex（后端） | B1-B8，API 实现，数据库，集成，安全 | 视觉决策 |

### Codex 执行格式

每个后端任务用以下格式提交给 Codex：

```bash
codex exec "<task prompt>" \
  -C "D:\zzj Claude code\aluminum-bypass" \
  -s workspace-write \
  -c model_reasoning_effort="high"
```

---

## 验收标准（完全体定义）

全部满足以下条件时，系统达到"完全体"：

1. **功能完整**：所有页面对接真实 API，无 mock 数据残留
2. **离线可用**：移动端断网可填报，恢复后自动同步
3. **推送到位**：钉钉消息按时送达，异常实时告警
4. **数据闭环**：MES → 数据中枢 → 报表 → 钉钉推送 全链路通
5. **可观测**：错误可追溯，性能可度量，业务指标可监控
6. **安全合规**：认证完整，权限隔离，审计可查
7. **自动化**：CI/CD 全流程，定时任务自动执行
8. **测试覆盖**：前端 E2E 已可执行并实跑通过（Chromium `112 passed / 3 skipped`，Mobile `21 passed`，A11y `12 passed`），后端 pytest 与完全体门禁纳入 `backend/scripts/check_full_completion_gate.py`

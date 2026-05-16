# 数据中枢 后端完全体方案

**Date:** 2026-05-16
**Executor:** Codex（后端逻辑 + 集成 + 基础设施）
**Base:** `D:\zzj Claude code\aluminum-bypass\backend`
**Branch:** `codex/gai`

## 当前状态

- FastAPI 应用，32 路由模块，70+ 服务
- 829 测试通过，3 skipped
- 17 数据模型文件覆盖全业务域
- SSE 实时推送已实现（event_bus + StreamingResponse）
- DingTalkService 是 placeholder（框架在，逻辑空）
- NullMesAdapter 兜底（适配器接口完整，无真实实现）
- LLM 适配器框架在（llm.py），assistant_service 有 mock fallback
- alembic 只有 001 placeholder migration
- 无定时任务引擎（无 Celery/APScheduler）
- Docker + docker-compose 已有
- 无 CI/CD pipeline
- 无 /health 或 /metrics 端点

## 约束

- Python 3.11+，FastAPI，SQLAlchemy 2.0，Pydantic v2
- 不引入重量级框架（不用 Celery，用 APScheduler）
- 不改现有 API 契约（只新增端点）
- 每个任务独立可提交，测试全绿

---

## B1. 钉钉推送完整实现

**目标：** 填报提醒、异常告警、审批通知通过钉钉工作通知送达

**交付物：**
- 修改 `app/services/dingtalk_service.py`（实现真实 API 调用）
- 新建 `app/services/dingtalk_templates.py`（消息模板）
- 新建 `tests/test_dingtalk_service.py`

**实现：**
```python
# app/services/dingtalk_service.py
import httpx
import time
from app.config import settings

class DingTalkService:
    def __init__(self):
        self.config = DingTalkConfig(...)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://oapi.dingtalk.com/gettoken",
                params={"appkey": self.config.app_key, "appsecret": self.config.app_secret}
            )
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + data["expires_in"]
        return self._access_token

    async def send_work_notification(self, user_id: str, msg: dict) -> bool:
        token = await self._ensure_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2",
                params={"access_token": token},
                json={"agent_id": self.config.agent_id, "userid_list": user_id, "msg": msg}
            )
            return resp.json().get("errcode") == 0

    async def send_group_message(self, chat_id: str, msg: dict) -> bool:
        token = await self._ensure_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oapi.dingtalk.com/chat/send",
                params={"access_token": token},
                json={"chatid": chat_id, "msg": msg}
            )
            return resp.json().get("errcode") == 0
```

**消息模板：**
```python
# app/services/dingtalk_templates.py
def build_fill_reminder(worker_name: str, shift: str, deadline: str) -> dict:
    return {
        "msgtype": "action_card",
        "action_card": {
            "title": f"填报提醒 - {shift}",
            "markdown": f"**{worker_name}**，{shift}班次数据尚未填报。\n\n截止时间：{deadline}",
            "single_title": "立即填报",
            "single_url": "dingtalk://dingtalkclient/page/link?url=..."
        }
    }

def build_anomaly_alert(workshop: str, metric: str, value: float, threshold: float) -> dict:
    return {
        "msgtype": "action_card",
        "action_card": {
            "title": f"异常告警 - {workshop}",
            "markdown": f"**{workshop}** {metric} 异常\n\n当前值：{value}\n阈值：{threshold}",
            "single_title": "查看详情",
            "single_url": "dingtalk://dingtalkclient/page/link?url=..."
        }
    }

def build_approval_notice(report_id: int, submitter: str, action: str) -> dict:
    return {
        "msgtype": "text",
        "text": {"content": f"报表 #{report_id}（{submitter}提交）已{action}"}
    }
```

**验收：**
1. `pytest tests/test_dingtalk_service.py` 全绿
2. 配置真实凭据后，`send_work_notification` 可送达
3. token 过期后自动刷新（mock time 测试）
4. 限流保护：连续发送 > 20条/秒 时排队

---

## B2. MES 真实适配器

**目标：** 与鑫泰 MES 系统实时数据同步

**交付物：**
- 新建 `app/adapters/xintai_mes_adapter.py`
- 修改 `app/core/deps.py` 根据配置选择适配器
- 新建 `tests/test_xintai_mes_adapter.py`

**实现：**
```python
# app/adapters/xintai_mes_adapter.py
import httpx
from app.adapters.mes_adapter import MesAdapter, CardInfo, CoilSnapshot, ScheduleItem

class XintaiMesAdapter(MesAdapter):
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base_url}/cards/{card_no}", headers=self._headers())
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return CardInfo(
                card_no=data["card_no"],
                alloy=data.get("alloy"),
                width_mm=data.get("width"),
                thickness_mm=data.get("thickness"),
                weight_kg=data.get("weight"),
                current_process=data.get("process"),
                workshop_name=data.get("workshop"),
            )

    def list_coil_snapshots(self, *, cursor=None, updated_after=None, limit=200):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if updated_after:
            params["updated_after"] = updated_after.isoformat()
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base_url}/coils", headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()
            snapshots = [CoilSnapshot(**item) for item in data["items"]]
            return snapshots, data.get("next_cursor")

    def get_daily_schedule(self, business_date, workshop):
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base_url}/schedule",
                headers=self._headers(),
                params={"date": business_date.isoformat(), "workshop": workshop}
            )
            resp.raise_for_status()
            return [ScheduleItem(**item) for item in resp.json()["items"]]

    def push_completion(self, card_no, output_weight, yield_rate) -> bool:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}/completions",
                headers=self._headers(),
                json={"card_no": card_no, "output_weight": output_weight, "yield_rate": yield_rate}
            )
            return resp.status_code in (200, 201, 409)  # 409 = 幂等重复
```

**适配器选择：**
```python
# app/core/deps.py 添加
def get_mes_adapter() -> MesAdapter:
    if settings.MES_API_BASE and settings.MES_API_KEY:
        return XintaiMesAdapter(settings.MES_API_BASE, settings.MES_API_KEY)
    return NullMesAdapter()
```

**前置条件：** 需要 MES API 文档 + 测试环境凭据

**验收：**
1. `pytest tests/test_xintai_mes_adapter.py` 全绿（httpx mock）
2. 配置真实凭据后，`get_tracking_card_info("实际卡号")` 返回数据
3. `push_completion` 重复调用返回 True（幂等）

---

## B3. 定时任务引擎

**目标：** 周期性业务逻辑自动执行

**交付物：**
- 新建 `app/core/scheduler.py`
- 新建 `app/tasks/__init__.py`
- 新建 `app/tasks/daily_report.py`
- 新建 `app/tasks/mes_sync.py`
- 新建 `app/tasks/fill_reminder.py`
- 新建 `app/tasks/data_archive.py`
- 修改 `app/main.py` lifespan 启动 scheduler
- 新建 `tests/test_scheduler.py`

**实现：**
```python
# app/core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

def setup_scheduler():
    from app.tasks.daily_report import generate_daily_reports
    from app.tasks.mes_sync import sync_mes_coil_snapshots
    from app.tasks.fill_reminder import send_fill_reminders
    from app.tasks.data_archive import archive_old_data

    scheduler.add_job(generate_daily_reports, CronTrigger(hour=6, minute=0), id="daily_report")
    scheduler.add_job(sync_mes_coil_snapshots, IntervalTrigger(minutes=30), id="mes_sync")
    scheduler.add_job(send_fill_reminders, CronTrigger(hour="8,14,20", minute=0), id="fill_reminder")
    scheduler.add_job(archive_old_data, CronTrigger(day_of_week="sun", hour=2), id="data_archive")

# app/tasks/daily_report.py
async def generate_daily_reports():
    """生成前日所有车间的班次汇总报表"""
    from app.core.deps import get_db_context
    from app.services.report_service import generate_shift_summary
    from datetime import date, timedelta

    yesterday = date.today() - timedelta(days=1)
    async with get_db_context() as db:
        await generate_shift_summary(db, business_date=yesterday)

# app/tasks/mes_sync.py
async def sync_mes_coil_snapshots():
    """增量同步 MES 铝卷快照"""
    from app.core.deps import get_db_context, get_mes_adapter
    from app.services.mes_sync_service import incremental_sync

    adapter = get_mes_adapter()
    async with get_db_context() as db:
        await incremental_sync(db, adapter)

# app/tasks/fill_reminder.py
async def send_fill_reminders():
    """发送未填报提醒"""
    from app.core.deps import get_db_context
    from app.services.mobile_reminder_service import find_unfilled_workers
    from app.services.dingtalk_service import DingTalkService
    from app.services.dingtalk_templates import build_fill_reminder

    dingtalk = DingTalkService()
    async with get_db_context() as db:
        workers = await find_unfilled_workers(db)
        for w in workers:
            msg = build_fill_reminder(w.name, w.shift, w.deadline)
            await dingtalk.send_work_notification(w.dingtalk_id, msg)

# app/tasks/data_archive.py
async def archive_old_data(days_before: int = 90):
    """归档 N 天前的历史数据到归档表"""
    from app.core.deps import get_db_context
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=days_before)
    async with get_db_context() as db:
        # 移动旧 shift_production 到 shift_production_archive
        # 移动旧 import_rows 到 import_rows_archive
        pass  # 具体实现依赖归档表结构
```

**修改 main.py：**
```python
# app/main.py lifespan
from contextlib import asynccontextmanager
from app.core.scheduler import scheduler, setup_scheduler

@asynccontextmanager
async def lifespan(app):
    setup_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()
```

**验收：**
1. `pytest tests/test_scheduler.py` 全绿
2. 启动应用后 scheduler 日志显示 4 个 job 注册
3. 手动触发 `generate_daily_reports()` 无报错

---

## B4. 数据库迁移正规化

**目标：** `alembic upgrade head` 可从空库建出完整 schema

**交付物：**
- 删除 `alembic/versions/001_initial_migration.py`
- 生成真实迁移：`alembic revision --autogenerate -m "full_schema"`
- 新建 `scripts/seed_production.py`（调用 real_master_data.seed）
- 修改 `alembic/env.py` 确保 import 所有 models

**步骤：**
```bash
# 1. 确保 env.py 导入所有 model
# 2. 删除旧 placeholder
rm alembic/versions/001_initial_migration.py
# 3. 生成真实迁移
alembic revision --autogenerate -m "full_schema_from_models"
# 4. 验证
alembic upgrade head      # 从空库建表
alembic downgrade base    # 回滚
alembic upgrade head      # 再次升级（幂等）
# 5. seed
python scripts/seed_production.py
```

**验收：**
1. 空 SQLite 数据库 `alembic upgrade head` 成功
2. `alembic downgrade -1` + `alembic upgrade head` 无报错
3. `scripts/seed_production.py` 执行后基础数据就位
4. 所有现有测试仍然通过

---

## B5. AI 助手接入真实 LLM

**目标：** AI 助手从 mock 切换到真实 LLM 响应

**交付物：**
- 修改 `app/services/assistant_service.py`（LLM 优先，mock fallback）
- 修改 `app/adapters/llm.py`（添加 usage tracking）
- 新建 `app/models/assistant_usage.py`（token 用量表）
- 新建 `tests/test_assistant_llm_integration.py`

**修改逻辑：**
```python
# app/services/assistant_service.py
async def query_assistant(db, payload, current_user):
    if not settings.LLM_ENABLED:
        return _build_mock_query_response(payload)
    
    try:
        context = await ai_context_service.build_context(db, current_user)
        rules = ai_rules_service.get_rules_for_mode(payload.mode)
        
        response = await llm_adapter.chat(
            system=rules,
            messages=[{"role": "user", "content": f"{context}\n\n{payload.query}"}],
            max_tokens=4096,
        )
        
        # 记录用量
        record_usage(db, user_id=current_user.id, 
                     input_tokens=response.usage.input, 
                     output_tokens=response.usage.output)
        
        return AssistantQueryResponseOut(
            mode=payload.mode, mock=False,
            summary=response.content, cards=[], 
            integrations_used=list(_DEFAULT_INTEGRATIONS_USED),
            next_actions=extract_actions(response.content),
        )
    except Exception:
        return _build_mock_query_response(payload)
```

**成本控制：**
- 单次请求 max_tokens=4096
- 每用户每日上限 50 次查询
- 超限返回友好提示而非报错

**验收：**
1. 配置 LLM_API_BASE + LLM_API_KEY 后，助手返回真实回答
2. 未配置时仍返回 mock（向后兼容）
3. `assistant_usage` 表记录每次调用的 token 数
4. 超过每日限额返回 429

---

## B6. 监控 + 遥测端点

**目标：** 生产环境可观测

**交付物：**
- 新建 `app/routers/health.py`
- 新建 `app/routers/telemetry.py`
- 新建 `app/schemas/telemetry.py`
- 修改 `app/core/logging.py`（结构化 JSON 日志）
- 新建 `tests/test_health.py`
- 新建 `tests/test_telemetry.py`

**实现：**
```python
# app/routers/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.config import settings

router = APIRouter(tags=["ops"])

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "db": "ok" if db_ok else "unreachable",
    }

# app/routers/telemetry.py
from fastapi import APIRouter
from app.schemas.telemetry import ErrorReport, PerfReport

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

@router.post("/errors")
async def receive_error(payload: ErrorReport):
    logger.warning("frontend_error", extra=payload.model_dump())
    return {"received": True}

@router.post("/perf")
async def receive_perf(payload: PerfReport):
    logger.info("frontend_perf", extra=payload.model_dump())
    return {"received": True}

# app/schemas/telemetry.py
from pydantic import BaseModel

class ErrorReport(BaseModel):
    message: str
    stack: str | None = None
    url: str
    info: str | None = None
    user_agent: str | None = None

class PerfReport(BaseModel):
    route: str
    metric: str
    value: float
    user_agent: str | None = None
```

**验收：**
1. `GET /health` 返回 200 + JSON
2. `POST /api/v1/telemetry/errors` 接收并记录
3. 日志输出为 JSON 格式（可被 ELK 采集）

---

## B7. 安全加固

**目标：** 生产环境安全基线

**交付物：**
- 修改 `app/core/auth.py`（添加 refresh token）
- 修改 `app/config.py`（CORS 收紧）
- 新建 `app/core/security.py`（文件上传校验）
- 修改 `app/routers/auth.py`（refresh 端点）
- 新建 `tests/test_security.py`

**实现要点：**

1. **JWT Refresh Token：**
```python
# access token: 15min, refresh token: 7d
@router.post("/auth/refresh")
def refresh_token(refresh: str = Body(...)):
    payload = decode_refresh_token(refresh)
    new_access = create_access_token(sub=payload["sub"])
    return {"access_token": new_access, "token_type": "bearer"}
```

2. **CORS 收紧：**
```python
# app/main.py
if settings.ENVIRONMENT == "production":
    origins = ["https://data.xintai-alu.com", "https://m.xintai-alu.com"]
else:
    origins = ["*"]
```

3. **文件上传安全：**
```python
# app/core/security.py
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".png", ".jpg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_upload(file: UploadFile):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(400, "文件大小超过 10MB 限制")
```

4. **全局 Rate Limit：**
```python
# 已有 app/core/rate_limit.py，确保全局应用
# 100 req/min/IP for API, 10 req/min/IP for auth
```

**验收：**
1. refresh token 流程：access 过期 → 用 refresh 换新 access
2. 生产 CORS 只允许指定域名
3. 上传 .exe 文件返回 400
4. 暴力登录 > 10次/分钟 返回 429

---

## B8. CI/CD Pipeline

**目标：** 代码提交到部署全自动化

**交付物：**
- `.github/workflows/ci.yml`
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-prod.yml`
- 修改 `Dockerfile`（多阶段构建优化）

**CI workflow：**
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
      - run: cd backend && python -m pytest --tb=short -q
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run build && node --test
```

**Deploy workflow：**
```yaml
# .github/workflows/deploy-prod.yml
name: Deploy Production
on:
  workflow_dispatch:
    inputs:
      confirm: { description: "Type 'deploy' to confirm", required: true }
jobs:
  deploy:
    if: github.event.inputs.confirm == 'deploy'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t xintai-backend ./backend
      - run: docker build -t xintai-frontend ./frontend
      # SSH deploy to 8.140.218.13
```

**验收：**
1. Push 触发 CI，lint + test 全绿
2. 手动触发 deploy-prod 需要输入确认
3. Docker 镜像构建成功

---

## 执行顺序

```
Phase A（上线阻塞，并行）:
  B4 (迁移) → B7 (安全) → B1 (钉钉)

Phase B（核心体验）:
  B3 (定时任务) → B6 (监控)

Phase C（增值）:
  B2 (MES) + B5 (AI 助手) + B8 (CI/CD)
```

## 依赖图

```
B4 (迁移正规化)
 ├──→ B3 (定时任务，依赖表结构稳定)
 │     ├──→ B1 (钉钉提醒需要定时调度)
 │     └──→ B2 (MES 同步需要定时调度)
 └──→ B5 (AI 助手需要 usage 表)

B7 (安全加固) ──→ B8 (CI/CD 需要安全配置)
B6 (监控端点) ←── 前端 F2 (错误上报依赖此端点)
```

## Codex 执行命令模板

```bash
codex exec "<paste task prompt here>" \
  -C "D:\zzj Claude code\aluminum-bypass" \
  -s workspace-write \
  -c model_reasoning_effort="high"
```

## 完成标志

- [ ] `alembic upgrade head` 从空库建表成功
- [ ] 钉钉推送真实送达
- [ ] MES 适配器对接真实系统
- [ ] 定时任务 4 个 job 运行正常
- [ ] AI 助手返回真实 LLM 回答
- [ ] /health 端点返回 200
- [ ] refresh token 流程通
- [ ] CI pipeline 全绿
- [ ] 829+ 测试全绿

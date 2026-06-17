# 07:30 Forecast, 09:30 Final Report, and Role Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `鑫泰铝业 数据中枢` 每天 07:30 自动生成可看的生产预报，09:30 自动生成终报，同时把确认无近用的旧角色从代码和数据入口里直接拆掉。

**Architecture:** 复用现有 `daily_reports` 表和现有日报汇总逻辑，不新增大表。07:30 预报用独立 `report_type='production_forecast'` 保存，避免覆盖 09:30 的正式 `production` 终报；角色删除先做可重复的生产库审计，再删除无近用角色名和别名，`consumable_stat` 因生产库最近仍在用，先保留并设迁移门槛。

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, Pytest, Vue 3, Node test runner, existing report/mapping reconciliation services.

---

## 先说清楚

这份计划不做历史兼容。旧角色一旦进入删除清单，就不是“隐藏”或“停用”，而是从登录入口、权限别名、模板可写角色、前端显示和测试里移除。

但是“直接删除”必须满足一个硬条件：确认不会断数据链路。生产库最近 7 天审计结果显示：

- `consumable_stat` 最近仍有人登录、扫码和写入 `work_order_entries`，不能现在删。
- `qc` 只有 1 个不活跃用户，最近无使用。
- `contracts`、`inventory_keeper`、`utility_manager`、`mobile_user`、`team_leader`、`deputy_leader`、`shift_leader`、`statistician`、`stat`、`reviewer` 没看到最近真实使用，可进入删除审计和拆除清单。
- `OP` 虚拟二维码全是停用状态，可清掉剩余入口引用。

外部数据判断：

- MES SQL Server 07:30 已能提供大部分生产、库存、合同数据，但出库类数据可能有 07:30 以后补齐的情况。
- 能源 MySQL 端口能连通，但连接握手超时，不能作为 07:30 稳定实时源。
- 所以 07:30 做“预报”，09:30 做“终报”；`D:\输出skill` 继续作为对账样本，不把外部数据库账号写进代码。

## 文件结构

### 后端日报

- Modify: `backend/app/tasks/daily_report.py`
  - 增加 `generate_forecast_daily_report()`。
  - 增加 `generate_final_daily_report()`。
  - 保留 `generate_daily_reports()` 作为旧函数名的薄包装，避免调度入口一次性大改。

- Modify: `backend/app/core/scheduler.py`
  - 把当前 08:00 `daily_report` 拆成两个任务：
    - `daily_report_forecast`：每天 07:30。
    - `daily_report_final`：每天 09:30。

- Modify: `backend/app/services/report/_utils.py`
  - 增加常量 `PRODUCTION_FORECAST_REPORT_TYPE = 'production_forecast'`。
  - 不把 `production_forecast` 放进 `VALID_REPORT_TYPES` 的默认列表，避免 `/reports/generate` 无意生成预报。

- Modify: `backend/app/services/report/report_generation.py`
  - 增加 `generate_production_stage_report()`，内部复用 `_generate_report_payload(... report_type='production')`。
  - 写入 `report_data.report_stage`、`report_data.stage_label`、`report_data.generated_cutoff_label`、`is_final_version`。

- Modify: `backend/app/services/report/dashboard_builder.py`
  - 给管理驾驶舱返回最近预报和终报的状态摘要，前端不用再猜。

- Modify: `backend/app/schemas/reports.py`
  - 如果新增接口需要请求体，再加轻量 schema；不要扩默认 `ReportGenerateRequest.report_type`。

### 后端角色删除

- Create: `backend/app/services/legacy_role_cleanup_service.py`
  - 只负责角色审计、删除门槛判断、删除计划构建。
  - 不直接读外部数据库。

- Create: `backend/scripts/audit_legacy_roles.py`
  - 只读脚本，输出哪些角色可删、哪些角色阻塞。

- Create: `backend/scripts/delete_legacy_roles.py`
  - 默认 dry-run。
  - 只有传 `--commit` 且审计全部通过时才真正删除。

- Modify: `backend/app/core/scope.py`
  - 从 `REVIEWER_ROLES`、`WORK_ORDER_GLOBAL_ENTRY_ROLES` 等集合里删除旧角色。

- Modify: `backend/app/core/field_permissions.py`
  - 删除旧角色别名。
  - 把旧写权限替换成新 owner 角色。

- Modify: `backend/app/core/field_lock.py`
  - 删除旧角色状态流转。
  - 保留新 owner 角色状态流转。

- Modify: `backend/app/core/templates/__init__.py`
  - 模板里的 `role_write` / `role_read` 删除旧角色名。

- Modify: `backend/app/core/templates/permissions.py`
  - 默认质检字段写入角色改为 `quality_owner`。
  - 注意：`qc_payload` 是现有数据字段名，本计划只删角色名，不做数据库列改名。

- Modify: `backend/app/services/work_order/_utils.py`
  - 删除旧角色 allowlist。

- Modify: `backend/app/services/work_order/entry.py`
  - 把 `normalize_role(operator.role) == 'qc'` 改成 `quality_owner`。

- Modify: `backend/app/services/mobile_report/shift_context.py`
  - 删除 `utility_manager`、`inventory_keeper`、`contracts`、`qc` 的入口模式兼容。

- Modify: `backend/app/services/real_master_data.py`
  - 删除 `RETIRED_ROLE_QR_SUFFIXES` 里已经停用且不再显示的旧入口。
  - 保留当前生产仍需要的 `consumable_stat` 主数据。

- Modify: `scripts/g7_role_cleanup.py`
  - 改成调用新的删除审计服务，或者删除这个旧“只停用”脚本。

### 前端

- Modify: `frontend/src/composables/useDashboardSnapshot.js`
  - 读取后端返回的 `daily_report_stage`，给今日页显示预报/终报状态。

- Modify: `frontend/src/views/manage/today/TodayPage.vue`
  - 在“日报结算”区域加一个紧凑状态条：
    - 07:30 预报：已生成 / 未生成 / 数据不足。
    - 09:30 终报：已生成 / 等待补齐 / 已推送。
  - 不加教学文案，不做新 landing。

- Modify: `frontend/src/utils/manageDailyReportSurface.js`
  - 增加一个纯函数 `buildDailyReportStageSummary()`，方便测试。

- Modify: `frontend/src/utils/display.js`
  - 删除旧角色显示文案。
  - 保留新角色显示文案和 `consumable_stat`。

- Modify: `frontend/src/views/mobile/MobileEntry.vue`
  - 删除旧角色颜色和入口列表。
  - 保留 `consumable_stat`。

- Modify: `frontend/src/views/manage/live/LiveDashboardPage.vue`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
  - 删除 `statistician` / `stat` 判断，改用后端返回的 manager/reviewer 能力或现有 active role。

### 测试

- Modify: `backend/tests/test_daily_report_task.py`
- Modify: `backend/tests/test_scheduler.py`
- Create: `backend/tests/test_report_stage_generation.py`
- Create: `backend/tests/test_legacy_role_cleanup_service.py`
- Modify: `backend/tests/test_workshop_templates.py`
- Modify: `backend/tests/test_work_order_permissions.py`
- Modify: `backend/tests/test_work_order_service.py`
- Modify: `backend/tests/test_work_order_routes.py`
- Modify: `frontend/tests/manageTodayPage.test.js`
- Modify: `frontend/tests/manageDailyReportSurface.test.js`
- Modify: `frontend/tests/displayNumberFormatting.test.js`
- Modify: `frontend/tests/mobileTransition.test.js`
- Modify: `frontend/tests/teamLeadShell.test.js`

---

## Task 1: 给日报加“预报/终报”生成能力

**Files:**
- Modify: `backend/app/services/report/_utils.py`
- Modify: `backend/app/services/report/report_generation.py`
- Create: `backend/tests/test_report_stage_generation.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_report_stage_generation.py` 写两个测试：

```python
from datetime import date

from app.models.reports import DailyReport
from app.services.report import report_generation
from app.services.report._utils import PRODUCTION_FORECAST_REPORT_TYPE


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *_args):
        return self

    def first(self):
        return self.db.report


class FakeReportDB:
    def __init__(self):
        self.report = None
        self.committed = False

    def query(self, model):
        assert model is DailyReport
        return FakeQuery(self)

    def add(self, entity):
        self.report = entity

    def flush(self):
        if self.report is not None and self.report.id is None:
            self.report.id = 1

    def commit(self):
        self.committed = True

    def refresh(self, _entity):
        return None


def test_generate_forecast_uses_separate_report_type(monkeypatch):
    db = FakeReportDB()
    monkeypatch.setattr(
        report_generation,
        '_generate_report_payload',
        lambda db, report_date, report_type, scope: (
            {'report_date': report_date.isoformat(), 'total_output_weight': 12.5},
            '预报摘要',
        ),
    )
    monkeypatch.setattr(report_generation, 'record_audit', lambda *args, **kwargs: None)

    reports = report_generation.generate_production_stage_report(
        db,
        report_date=date(2026, 6, 16),
        stage='forecast',
        scope='auto_confirmed',
        output_mode='both',
        operator=None,
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.report_type == PRODUCTION_FORECAST_REPORT_TYPE
    assert report.report_data['report_stage'] == 'forecast'
    assert report.report_data['stage_label'] == '07:30预报'
    assert report.is_final_version is False


def test_final_stage_keeps_existing_production_report_type(monkeypatch):
    db = FakeReportDB()
    monkeypatch.setattr(
        report_generation,
        '_generate_report_payload',
        lambda db, report_date, report_type, scope: (
            {'report_date': report_date.isoformat(), 'total_output_weight': 20},
            '终报摘要',
        ),
    )
    monkeypatch.setattr(report_generation, 'record_audit', lambda *args, **kwargs: None)

    reports = report_generation.generate_production_stage_report(
        db,
        report_date=date(2026, 6, 16),
        stage='final',
        scope='auto_confirmed',
        output_mode='both',
        operator=None,
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.report_type == 'production'
    assert report.report_data['report_stage'] == 'final'
    assert report.report_data['stage_label'] == '09:30终报'
    assert report.is_final_version is True
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_report_stage_generation.py -q
```

Expected: FAIL，提示 `generate_production_stage_report` 或 `PRODUCTION_FORECAST_REPORT_TYPE` 不存在。

- [ ] **Step 3: 写最小实现**

在 `backend/app/services/report/_utils.py` 增加：

```python
PRODUCTION_FORECAST_REPORT_TYPE = 'production_forecast'
```

在 `backend/app/services/report/report_generation.py` 增加函数。实现要复用 `_generate_report_payload(... report_type='production')`，不要复制生产日报算法。

关键逻辑：

```python
def generate_production_stage_report(
    db: Session,
    *,
    report_date: date,
    stage: str,
    scope: str,
    output_mode: str,
    operator: User | None,
) -> list[DailyReport]:
    if stage not in {'forecast', 'final'}:
        raise ValueError('stage must be forecast or final')
    report_type = PRODUCTION_FORECAST_REPORT_TYPE if stage == 'forecast' else 'production'
    label = '07:30预报' if stage == 'forecast' else '09:30终报'

    report_data, text_summary = _generate_report_payload(
        db,
        report_date=report_date,
        report_type='production',
        scope=_normalize_scope(scope),
    )
    report_data = dict(report_data or {})
    report_data['report_stage'] = stage
    report_data['stage_label'] = label
    report_data['generated_cutoff_label'] = label

    # Upsert DailyReport by report_date + report_type, same style as generate_daily_reports().
```

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend
pytest tests/test_report_stage_generation.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/report/_utils.py backend/app/services/report/report_generation.py backend/tests/test_report_stage_generation.py
git commit -m "feat: add staged production report generation"
```

---

## Task 2: 调度改成 07:30 预报、09:30 终报

**Files:**
- Modify: `backend/app/tasks/daily_report.py`
- Modify: `backend/app/core/scheduler.py`
- Modify: `backend/tests/test_daily_report_task.py`
- Modify: `backend/tests/test_scheduler.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_daily_report_task.py` 增加：

```python
def test_generate_forecast_daily_report_writes_forecast(monkeypatch):
    session = FakeSession()
    calls = []
    monkeypatch.setattr(daily_report, 'last_completed_production_business_date', lambda: date(2026, 6, 16))
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        daily_report.report_service,
        'generate_production_stage_report',
        lambda db, report_date, stage, scope, output_mode, operator: calls.append((db, report_date, stage)),
    )

    result = daily_report.generate_forecast_daily_report()

    assert result == {'status': 'ok', 'business_date': '2026-06-16', 'stage': 'forecast'}
    assert calls == [(session, date(2026, 6, 16), 'forecast')]
```

在 `backend/tests/test_scheduler.py` 把旧断言：

```python
assert scheduler.jobs['daily_report']['kwargs']['hour'] == 8
```

改成：

```python
assert scheduler.jobs['daily_report_forecast']['kwargs']['hour'] == 7
assert scheduler.jobs['daily_report_forecast']['kwargs']['minute'] == 30
assert scheduler.jobs['daily_report_final']['kwargs']['hour'] == 9
assert scheduler.jobs['daily_report_final']['kwargs']['minute'] == 30
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_daily_report_task.py tests/test_scheduler.py -q
```

Expected: FAIL，提示新函数或新 job id 不存在。

- [ ] **Step 3: 写实现**

`backend/app/tasks/daily_report.py`：

- `generate_forecast_daily_report()` 调用 `report_service.generate_production_stage_report(... stage='forecast')`。
- `generate_final_daily_report()` 先跑现有 aggregator/reporter 链路，再把 `production` 报告标记成 final。
- `generate_daily_reports()` 保留为调用 `generate_final_daily_report()` 的包装，避免别处老函数名直接炸。

`backend/app/core/scheduler.py`：

```python
from app.tasks.daily_report import generate_forecast_daily_report, generate_final_daily_report

_add_job_once(active_scheduler, generate_forecast_daily_report, 'cron', job_id='daily_report_forecast', hour=7, minute=30)
_add_job_once(active_scheduler, generate_final_daily_report, 'cron', job_id='daily_report_final', hour=9, minute=30)
```

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend
pytest tests/test_daily_report_task.py tests/test_scheduler.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/tasks/daily_report.py backend/app/core/scheduler.py backend/tests/test_daily_report_task.py backend/tests/test_scheduler.py
git commit -m "feat: schedule forecast and final daily reports"
```

---

## Task 3: 给今日页显示预报/终报状态

**Files:**
- Modify: `backend/app/services/report/dashboard_builder.py`
- Modify: `frontend/src/composables/useDashboardSnapshot.js`
- Modify: `frontend/src/utils/manageDailyReportSurface.js`
- Modify: `frontend/src/views/manage/today/TodayPage.vue`
- Modify: `frontend/tests/manageDailyReportSurface.test.js`
- Modify: `frontend/tests/manageTodayPage.test.js`

- [ ] **Step 1: 后端测试先补**

优先用已有 dashboard 测试补断言，位置看当前适配点：

```bash
cd backend
pytest tests/test_dashboard_routes.py tests/test_factory_dashboard_sanity.py -q
```

如果现有测试夹具不适合，就新增一个小测试，断言 dashboard payload 里有：

```python
{
    'daily_report_stage': {
        'forecast': {'status': 'generated' | 'missing'},
        'final': {'status': 'generated' | 'missing'}
    }
}
```

- [ ] **Step 2: 前端写纯函数测试**

在 `frontend/tests/manageDailyReportSurface.test.js` 增加：

```javascript
import { buildDailyReportStageSummary } from '../src/utils/manageDailyReportSurface.js'

test('daily report stage summary keeps forecast and final separate', () => {
  const summary = buildDailyReportStageSummary({
    forecast: { status: 'generated', generated_at: '2026-06-17T07:31:00+08:00' },
    final: { status: 'missing' }
  })

  assert.equal(summary.forecast.label, '07:30预报')
  assert.equal(summary.forecast.tone, 'success')
  assert.equal(summary.final.label, '09:30终报')
  assert.equal(summary.final.tone, 'warning')
})
```

- [ ] **Step 3: 运行前端测试确认失败**

Run:

```bash
cd frontend
npm test -- manageDailyReportSurface.test.js manageTodayPage.test.js
```

Expected: FAIL，提示函数或页面标识不存在。

- [ ] **Step 4: 实现 UI**

`TodayPage.vue` 只加一条紧凑状态条，放在日报结算区域附近。文案限制为短标签：

- `07:30预报`
- `09:30终报`
- `已生成`
- `待生成`
- `已推送`

不要加说明段落，不要做新卡片套卡片。

- [ ] **Step 5: 跑前后端相关测试**

Run:

```bash
cd backend
pytest tests/test_dashboard_routes.py tests/test_factory_dashboard_sanity.py -q
cd ../frontend
npm test -- manageDailyReportSurface.test.js manageTodayPage.test.js
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/report/dashboard_builder.py frontend/src/composables/useDashboardSnapshot.js frontend/src/utils/manageDailyReportSurface.js frontend/src/views/manage/today/TodayPage.vue frontend/tests/manageDailyReportSurface.test.js frontend/tests/manageTodayPage.test.js
git commit -m "feat: show daily report stage status"
```

---

## Task 4: 用 `D:\输出skill` 做终报对账样本

**Files:**
- Modify: `backend/app/services/mapping_reconciliation_service.py`
- Modify: `backend/app/routers/mapping_reconciliation.py`
- Modify: `backend/tests/test_mapping_reconciliation_service.py`
- Modify: `backend/tests/test_mapping_reconciliation_route.py`

注意：当前工作区这几个文件已经有未提交改动，执行前必须先看 `git diff -- backend/app/services/mapping_reconciliation_service.py backend/app/routers/mapping_reconciliation.py frontend/src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue`，不要覆盖别人改动。

- [ ] **Step 1: 写测试**

补一个按业务日期自动选文件的测试：

```python
def test_resolve_latest_output_skill_report_for_business_date(tmp_path):
    root = tmp_path
    (root / '2026-6-16_日报正文.txt').write_text('2026年6月16日 生产日报', encoding='utf-8')
    (root / '2026-6-16_核对记录.txt').write_text('核对记录', encoding='utf-8')

    result = resolve_output_skill_daily_report(root, business_date=date(2026, 6, 16))

    assert result.name == '2026-6-16_日报正文.txt'
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_mapping_reconciliation_service.py tests/test_mapping_reconciliation_route.py -q
```

Expected: FAIL，提示函数不存在。

- [ ] **Step 3: 实现最小能力**

在 `mapping_reconciliation_service.py` 增加：

- `resolve_output_skill_daily_report(reference_root, business_date)`
- 只选 `*_日报正文.txt`，不要选 `*_核对记录.txt`。
- 找不到时返回清晰错误，不自动猜别的日期。

在 route 里增加一个轻量 endpoint：

```python
@router.post('/run-output-skill-daily')
def run_output_skill_daily_reconciliation(...):
    # 解析 D:\输出skill 当天日报正文
    # 调用现有 compare_mapping_rows
    # 保存 MappingReconciliationRun
```

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend
pytest tests/test_mapping_reconciliation_service.py tests/test_mapping_reconciliation_route.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/mapping_reconciliation_service.py backend/app/routers/mapping_reconciliation.py backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py
git commit -m "feat: reconcile daily report with output skill sample"
```

---

## Task 5: 增加旧角色审计服务

**Files:**
- Create: `backend/app/services/legacy_role_cleanup_service.py`
- Create: `backend/tests/test_legacy_role_cleanup_service.py`
- Create: `backend/scripts/audit_legacy_roles.py`

- [ ] **Step 1: 写失败测试**

核心测试要覆盖三件事：

```python
def test_role_with_recent_login_is_blocked():
    # consumable_stat 最近登录，应 blocked


def test_unused_legacy_role_is_deletable():
    # contracts 没用户、没近 7 天引用，应 deletable


def test_role_with_foreign_key_reference_requires_manual_reassign():
    # qc 用户被历史业务表引用，脚本不能直接删用户
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_legacy_role_cleanup_service.py -q
```

Expected: FAIL，提示服务不存在。

- [ ] **Step 3: 实现审计服务**

建议常量：

```python
DELETE_CANDIDATE_ROLES = (
    'qc',
    'contracts',
    'inventory_keeper',
    'utility_manager',
    'mobile_user',
    'team_leader',
    'deputy_leader',
    'shift_leader',
    'statistician',
    'stat',
    'reviewer',
)

KEEP_UNTIL_MIGRATED_ROLES = ('consumable_stat',)
```

审计输出结构保持简单：

```python
{
    'role': 'qc',
    'decision': 'deletable' | 'blocked' | 'keep_until_migrated',
    'recent_login_count': 0,
    'recent_audit_count': 0,
    'recent_write_count': 0,
    'active_user_count': 0,
    'referenced_user_count': 0,
    'reasons': [],
}
```

- [ ] **Step 4: 实现只读脚本**

`backend/scripts/audit_legacy_roles.py`：

```python
from app.database import get_sessionmaker
from app.services.legacy_role_cleanup_service import audit_legacy_roles


def main() -> None:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        result = audit_legacy_roles(db, recent_days=7)
    for row in result:
        print(row)
```

- [ ] **Step 5: 跑测试和本地 dry-run**

Run:

```bash
cd backend
pytest tests/test_legacy_role_cleanup_service.py -q
python scripts/audit_legacy_roles.py
```

Expected: 测试 PASS；脚本只打印，不改数据库。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/legacy_role_cleanup_service.py backend/tests/test_legacy_role_cleanup_service.py backend/scripts/audit_legacy_roles.py
git commit -m "feat: audit legacy roles before deletion"
```

---

## Task 6: 从权限和模板里删除无近用旧角色

**Files:**
- Modify: `backend/app/core/scope.py`
- Modify: `backend/app/core/field_permissions.py`
- Modify: `backend/app/core/field_lock.py`
- Modify: `backend/app/core/templates/__init__.py`
- Modify: `backend/app/core/templates/permissions.py`
- Modify: `backend/app/services/work_order/_utils.py`
- Modify: `backend/app/services/work_order/entry.py`
- Modify: `backend/app/services/mobile_report/shift_context.py`
- Modify: `backend/tests/test_workshop_templates.py`
- Modify: `backend/tests/test_work_order_permissions.py`
- Modify: `backend/tests/test_work_order_service.py`
- Modify: `backend/tests/test_work_order_routes.py`
- Modify: `backend/tests/test_workshop_template_mobile_role_aliases.py`
- Modify: `backend/tests/test_workshop_template_power_roles.py`

- [ ] **Step 1: 先改测试口径**

把旧角色用例换成新角色：

- `qc` -> `quality_owner`
- `contracts` -> `planning_owner`
- `inventory_keeper` -> `storage_owner`
- `utility_manager` -> `energy_chief`
- `shift_leader` / `team_leader` / `deputy_leader` / `mobile_user` -> 删除兼容测试，不替换成“旧角色仍可用”断言
- `reviewer` / `statistician` / `stat` -> 删除兼容断言，管理端用 `manager` / `workshop_director` / `admin`

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd backend
pytest tests/test_workshop_templates.py tests/test_work_order_permissions.py tests/test_work_order_service.py tests/test_work_order_routes.py tests/test_workshop_template_mobile_role_aliases.py tests/test_workshop_template_power_roles.py -q
```

Expected: FAIL，因为代码还保留旧角色。

- [ ] **Step 3: 删除代码里的旧角色名**

按文件逐个改，不做大重构：

- `field_permissions.py`
  - 删除 `shift_leader`、`team_leader`、`deputy_leader`、`mobile_user`、`QC`、`UM`、`IK`、`CT` 别名。
  - `contract_no/customer_name/contract_weight` 写权限改 `planning_owner`。
  - `energy_kwh/gas_m3` 仍保留 `energy_stat`，全厂能源字段由 `energy_chief`。
  - `qc_grade/qc_notes/qc_payload` 写权限改 `quality_owner`。

- `field_lock.py`
  - 删除旧角色 transition。
  - 保留 owner transition。

- `templates/__init__.py`
  - 所有 `role_write` / `role_read` 中旧角色名替换成新 owner。

- `work_order/_utils.py`
  - allowlist 只留 active roles。

- `work_order/entry.py`
  - `normalize_role(operator.role) == 'qc'` 改为 `quality_owner`。

- `mobile_report/shift_context.py`
  - 删除旧 owner 兼容入口。

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend
pytest tests/test_workshop_templates.py tests/test_work_order_permissions.py tests/test_work_order_service.py tests/test_work_order_routes.py tests/test_workshop_template_mobile_role_aliases.py tests/test_workshop_template_power_roles.py -q
```

Expected: PASS。

- [ ] **Step 5: 搜索确认旧角色没有回流**

Run:

```bash
rg "shift_leader|team_leader|deputy_leader|mobile_user|utility_manager|inventory_keeper|contracts|statistician|reviewer|\\bstat\\b" backend/app backend/tests
```

Expected: 只允许出现在历史文档、删除脚本常量、测试删除清单里；不能出现在权限判断或用户入口。

- [ ] **Step 6: 提交**

```bash
git add backend/app/core/scope.py backend/app/core/field_permissions.py backend/app/core/field_lock.py backend/app/core/templates/__init__.py backend/app/core/templates/permissions.py backend/app/services/work_order/_utils.py backend/app/services/work_order/entry.py backend/app/services/mobile_report/shift_context.py backend/tests
git commit -m "refactor: remove unused legacy role permissions"
```

---

## Task 7: 前端删除旧角色入口

**Files:**
- Modify: `frontend/src/utils/display.js`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/manage/live/LiveDashboardPage.vue`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Modify: `frontend/tests/displayNumberFormatting.test.js`
- Modify: `frontend/tests/mobileTransition.test.js`
- Modify: `frontend/tests/teamLeadShell.test.js`

- [ ] **Step 1: 改测试**

`displayNumberFormatting.test.js` 不再期待：

- `qc`
- `utility_manager`
- `shift_leader`

新增断言：

```javascript
assert.equal(formatRoleLabel('quality_owner'), '全厂质检内勤')
assert.equal(formatRoleLabel('planning_owner'), '全厂计划内勤')
assert.equal(formatRoleLabel('energy_chief'), '全厂总电工')
assert.equal(formatRoleLabel('consumable_stat'), '生产内勤')
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd frontend
npm test -- displayNumberFormatting.test.js mobileTransition.test.js teamLeadShell.test.js
```

Expected: FAIL，旧角色仍在源码里。

- [ ] **Step 3: 删除前端旧角色**

- `display.js` 删除旧角色 label。
- `MobileEntry.vue` 删除旧角色颜色和角色列表。
- `LiveDashboardPage.vue` / `LiveDashboard.vue` 删除 `statistician` / `stat` 角色判断。

- [ ] **Step 4: 搜索确认**

Run:

```bash
rg "shift_leader|team_leader|deputy_leader|mobile_user|utility_manager|inventory_keeper|contracts|statistician|reviewer|\\bstat\\b" frontend/src frontend/tests
```

Expected: 只允许业务名“合同 contracts 路由/页面”出现；不能作为角色出现。

- [ ] **Step 5: 跑测试**

Run:

```bash
cd frontend
npm test -- displayNumberFormatting.test.js mobileTransition.test.js teamLeadShell.test.js manageTodayPage.test.js
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/utils/display.js frontend/src/views/mobile/MobileEntry.vue frontend/src/views/manage/live/LiveDashboardPage.vue frontend/src/views/reports/LiveDashboard.vue frontend/tests/displayNumberFormatting.test.js frontend/tests/mobileTransition.test.js frontend/tests/teamLeadShell.test.js
git commit -m "refactor: remove legacy role UI entries"
```

---

## Task 8: 增加真正删除脚本

**Files:**
- Create: `backend/scripts/delete_legacy_roles.py`
- Modify: `backend/app/services/legacy_role_cleanup_service.py`
- Modify: `backend/tests/test_legacy_role_cleanup_service.py`
- Modify: `scripts/g7_role_cleanup.py`

- [ ] **Step 1: 写测试**

测试规则：

```python
def test_delete_requires_commit_flag():
    # dry-run 不删除


def test_delete_aborts_when_role_blocked():
    # consumable_stat blocked，不允许删


def test_delete_removes_only_deletable_roles():
    # 只删除 audit decision == deletable 的 user rows / QR rows
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_legacy_role_cleanup_service.py -q
```

Expected: FAIL。

- [ ] **Step 3: 实现删除**

删除脚本规则：

- 默认 `python scripts/delete_legacy_roles.py` 只打印计划。
- `python scripts/delete_legacy_roles.py --commit` 才删除。
- 如果任一候选角色审计结果是 `blocked`，直接退出，不做部分删除。
- `consumable_stat` 永远不在本轮删除范围。
- 删除前打印：
  - 待删除角色
  - 待删除用户数
  - 待删除二维码数
  - 阻塞原因

- [ ] **Step 4: 跑测试和 dry-run**

Run:

```bash
cd backend
pytest tests/test_legacy_role_cleanup_service.py -q
python scripts/delete_legacy_roles.py
```

Expected: 测试 PASS；脚本 dry-run 不改库。

- [ ] **Step 5: 提交**

```bash
git add backend/scripts/delete_legacy_roles.py backend/app/services/legacy_role_cleanup_service.py backend/tests/test_legacy_role_cleanup_service.py scripts/g7_role_cleanup.py
git commit -m "feat: delete audited legacy roles"
```

---

## Task 9: 验证 07:30/09:30 数据链路

**Files:**
- No code changes expected.

- [ ] **Step 1: 跑后端相关测试**

Run:

```bash
cd backend
pytest tests/test_report_stage_generation.py tests/test_daily_report_task.py tests/test_scheduler.py tests/test_dashboard_routes.py tests/test_mapping_reconciliation_service.py tests/test_mapping_reconciliation_route.py tests/test_legacy_role_cleanup_service.py -q
```

Expected: PASS。

- [ ] **Step 2: 跑前端相关测试**

Run:

```bash
cd frontend
npm test -- manageDailyReportSurface.test.js manageTodayPage.test.js displayNumberFormatting.test.js mobileTransition.test.js teamLeadShell.test.js
```

Expected: PASS。

- [ ] **Step 3: 全局旧角色搜索**

Run:

```bash
rg "shift_leader|team_leader|deputy_leader|mobile_user|utility_manager|inventory_keeper|statistician|reviewer|\\bstat\\b" backend/app frontend/src
```

Expected: 无角色入口残留。`contracts` 作为“合同业务页面/字段”可出现，但不能作为用户角色判断出现。

- [ ] **Step 4: 本地手动跑一次预报和终报**

Run:

```bash
cd backend
@'
from datetime import date
from app.tasks.daily_report import generate_forecast_daily_report, generate_final_daily_report

target = date(2026, 6, 16)
print(generate_forecast_daily_report(target))
print(generate_final_daily_report(target))
'@ | python -
```

Expected:

- 第一行返回 `stage: forecast`。
- 第二行返回 `stage: final`。
- 数据库中同一天有 `production_forecast` 和 `production` 两条记录。

- [ ] **Step 5: 生产执行前再审计**

Run on production backend host:

```bash
cd /path/to/backend
python scripts/audit_legacy_roles.py
```

Expected:

- `consumable_stat` 是 `keep_until_migrated` 或 `blocked`。
- 删除候选角色全部是 `deletable` 才能执行 `delete_legacy_roles.py --commit`。

- [ ] **Step 6: 提交验证记录**

```bash
git status --short
git commit --allow-empty -m "test: verify forecast final report and role cleanup"
```

---

## 不做的事

- 不把外部数据库账号、密码、IP 写进代码或文档。
- 不在 07:30 强行生成“最终日报”。
- 不把能源 MySQL 当成 07:30 实时可靠源，除非连接握手问题先解决。
- 不删除 `consumable_stat`，直到最近使用清零或有明确替代角色承接它的填报链路。
- 不改 `qc_payload` 这类数据库字段名；本轮删除的是用户角色，不是历史数据列。

## 完成标准

- 07:30 有 `production_forecast`。
- 09:30 有 `production` 终报。
- 今日页能区分“预报”和“终报”。
- `D:\输出skill` 当天日报正文能被选中并参与对账。
- 无近用旧角色不再出现在登录、权限、模板、前端入口和测试保护里。
- `consumable_stat` 继续可用，且计划里明确了它不能现在删的原因。

## 执行方式

推荐先执行 Task 1-3，确认日报双阶段跑通；再执行 Task 5-8 删除角色。Task 4 依赖当前映射核对相关未提交改动，执行前先整理工作区。

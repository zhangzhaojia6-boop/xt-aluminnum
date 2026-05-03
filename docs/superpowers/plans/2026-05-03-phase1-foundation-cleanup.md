# Phase 1 · 地基清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `鑫泰铝业 数据中枢` 的地基干净可跑——readyz 硬阻断清零、pytest 收集红全消、企业微信代码路径下线（保留群机器人 publisher）、MES 投影为空时工厂指挥中心 7 屏不再白屏而是回退到 `ShiftProductionData`。

**Architecture:** 后端把 readiness 硬阻断的两个根因（设备绑定、排班空）收口为"空态可放行"或"一键修复"路径；删除 `routers/wecom.py` 与 `services/wecom_mapping_service.py`，把 `agents/reporter.py` 和 `agents/reminder.py` 的 `_send_*_message` 收敛到钉钉 + 站内日志，保留 `adapters/wecom/group_bot.py` 给 workflow publisher lane；`factory_command_service` 在 `freshness.status ∈ {unconfigured, migration_missing, failed}` 时直接从 `ShiftProductionData` / `MobileShiftReport` 聚合，让 7 屏有数。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Element Plus, node:test

---

## Scope

In scope:

- `EQUIPMENT_USER_BINDING_INVALID` 在"空绑定"状态下改为 warning，不拦 readyz；真正坏绑定（指向不存在设备）仍硬拦。
- `SCHEDULE_EMPTY` 在系统无任何排班数据时降级为 warning + 操作提示，有排班但今日为空才硬拦。
- 删除 `backend/app/routers/wecom.py`、`backend/app/services/wecom_mapping_service.py`、`backend/app/routers` 注册。
- `reporter.py` / `reminder.py` 的推送函数：钉钉分支优先 → 站内日志兜底；`WECOM_APP_ENABLED` 配置项标 deprecated，默认 false。
- 保留 `adapters/wecom/group_bot.py` + `adapters/workflow/registry.py` 的群机器人 publisher（它是输出通道，不是入口）。
- `factory_command_service` 的 `build_overview / list_workshops / list_machine_lines / list_coils` 在 MES 投影空时，按 `ShiftProductionData` 聚合出回退数据。
- pytest collection 问题：`backend/scripts/test_*.py` 从收集根目录排除；`.pytest_cache` 权限问题通过 `conftest.py` 统一 cache 目录解决。

Out of scope:

- 不改现有 agent 执行逻辑。
- 不改 MES adapter 代码。
- 不改前端 7 屏视觉，只换数据源。
- 不动 reviewer / statistician 兼容路由（留给 Phase 2/3）。
- 不引入新第三方依赖。

---

## Task 1: Pytest 收集与回归全绿

**Files:**

- Modify: `backend/pytest.ini` 或 `backend/pyproject.toml`
- Modify: `backend/conftest.py`（若不存在则新建）
- Move or rename: `backend/scripts/test_entry_fields.py` → `backend/scripts/smoke_entry_fields.py`
- Move or rename: `backend/scripts/test_shift.py` → `backend/scripts/smoke_shift.py`
- Test: 既有失败测试集（先跑一遍定位）

- [ ] **Step 1: 定位当前真实红测**

```powershell
python -m pytest backend/tests -q --no-header 2>&1 | Select-String "FAILED|ERROR" | Select-Object -First 30
```

记录失败 test 名与根因（RED）。

- [ ] **Step 2: 排除冒烟脚本与统一 cache 目录**

- `pytest.ini` 增加 `testpaths = backend/tests` 和 `norecursedirs = backend/scripts backend/pytest-cache-files-*`
- 在 `backend/conftest.py` 设置 `pytest_configure` 中显式指向 `cache_dir = .pytest_cache`（防止 Windows 多进程写临时 cache 失败）
- 把误命名的 `backend/scripts/test_*.py` 改名为 `smoke_*.py`

- [ ] **Step 3: 逐个修掉真实红测**

按 Step 1 的清单一个一个修。修一条提一次小 commit，避免"一坨"。

- [ ] **Step 4: 确认 GREEN**

```powershell
python -m pytest backend/tests -q
```

Expected: `0 failed, 0 error`.

- [ ] **Step 5: Commit**

Commit message: `test: 收口后端回归全绿`

---

## Task 2: Readyz 硬阻断降级

**Files:**

- Modify: `backend/app/core/health.py`
- Modify: `backend/app/services/config_readiness_service.py`
- Test: `backend/tests/test_health.py`
- Test: `backend/tests/test_config_readiness_service.py`

- [ ] **Step 1: 写失败测试**

测试必须 pin 住这几个状态：

- 数据库**无任何** `equipment_user_bindings` 记录：`checks.equipment_binding='warning'`，readyz 仍 200。
- 数据库有绑定但指向不存在设备：`checks.equipment_binding='error'`，readyz 503。
- 数据库**无任何**排班：`checks.schedule='warning'`，readyz 仍 200，`action_required='seed_schedule'`。
- 有排班但今日为空：`checks.schedule='error'`（保持现有硬拦）。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_health.py backend/tests/test_config_readiness_service.py -q
```

- [ ] **Step 3: 实现降级逻辑**

- `config_readiness_service`：新增 `evaluate_equipment_binding()`、`evaluate_schedule()`，各自返回 `{status: 'ok'|'warning'|'error', action_required, detail}`。
- `health.py`：聚合时只有 `error` 计入 `hard_issues`，`warning` 计入 `soft_issues` 并保持 overall `ready=True`。

- [ ] **Step 4: GREEN**

```powershell
python -m pytest backend/tests/test_health.py backend/tests/test_config_readiness_service.py backend/tests/test_main_readyz.py -q
```

- [ ] **Step 5: Commit**

Commit message: `feat: readyz 空绑定与空排班降级为 warning`

---

## Task 3: 拆除企业微信代码路径

**Files:**

- Delete: `backend/app/routers/wecom.py`
- Delete: `backend/app/services/wecom_mapping_service.py`
- Modify: `backend/app/routers/__init__.py`（取消 wecom 注册）
- Modify: `backend/app/main.py`（取消 import）
- Modify: `backend/app/agents/reporter.py`
- Modify: `backend/app/agents/reminder.py`
- Modify: `backend/app/config.py`（`WECOM_APP_ENABLED` 标 deprecated，不再被通知逻辑读取）
- Modify: `frontend/src/views/mobile/MobileEntry.vue`（文案与提示词统一为"钉钉"）
- Keep: `backend/app/adapters/wecom/group_bot.py`（workflow publisher lane 还在用）
- Keep: `backend/app/adapters/wecom/__init__.py`（只保留 `WeComGroupBotPublisher` 一个导出；删除 `get_access_token / code_to_userid / send_app_message / get_jsapi_ticket / generate_jsapi_signature`）
- Test: `backend/tests/test_wecom_*.py`（删除直接测试 OAuth / app message 的用例；保留 group_bot publisher 测试）
- Test: `backend/tests/test_agent_reporter_*.py`
- Test: `backend/tests/test_agent_reminder_*.py`

- [ ] **Step 1: 写失败测试**

- reporter agent 在 `DINGTALK_ENABLED=true` + user 有 `dingtalk_user_id` 时走钉钉分支；否则落站内日志。
- reminder agent 同上。
- 两者都不再引用 `WECOM_APP_ENABLED` / `send_app_message`。
- `from app.routers import wecom` 应当 `ImportError`。
- `WeComGroupBotPublisher` 仍可正常 import 与调用（保底回归）。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_agent_reporter.py backend/tests/test_agent_reminder.py backend/tests/test_wecom_group_bot.py -q
```

- [ ] **Step 3: 实现通道切换**

- `reporter.py:106 _send_message` → 改签名为 `_send_message(self, user, content)`，内部：
  - 若 `settings.DINGTALK_ENABLED` 且 `user.dingtalk_user_id`：调 `dingtalk_service.send_work_notification(...)`（若该函数不存在则先在 `dingtalk_service.py` 加一个 placeholder，返回 `(True, 'dingtalk_stub')`，留给 Phase 3 打通）。
  - 否则：`self.logger.info('[notify] %s | %s', user.username, content)` 返回 `(True, 'stdout_sink')`。
- `reminder.py:47 _send_reminder_message` 与 `_send_escalation_message` 同样替换；删除 `asyncio.run(send_app_message(...))`。
- 删除 `_wecom_userid` 函数；新增 `_resolve_notify_identity(user) -> tuple[channel, identity]`。
- `reporter.py` / `reminder.py` 顶部 import 的 `from app.adapters.wecom import send_app_message` 全部移除。

- [ ] **Step 4: 删除 router / service / 配置读取**

- 删 `routers/wecom.py`、`services/wecom_mapping_service.py` 与对应 import。
- `config.py` 保留 `WECOM_*` 字段（向前兼容 .env），但标注 `# deprecated: kept only for group bot publisher webhook URL`。
- `adapters/wecom/__init__.py` 精简到仅 `WeComGroupBotPublisher` 导出。
- `MobileEntry.vue` 把任何"企业微信"字样改成"钉钉"（grep 确认 `wx.config` / `wecom` 无前端引用）。

- [ ] **Step 5: GREEN + grep 验证**

```powershell
python -m pytest backend/tests -q
npm --prefix frontend test
```

```powershell
# 关键验证：wecom 只剩 group bot 路径
Select-String -Path "backend/app/**/*.py" -Pattern "WECOM|wecom" -SimpleMatch | Where-Object { $_.Line -notmatch "group_bot|WeComGroupBotPublisher|deprecated" }
```

Expected: 该 grep 输出为空。

- [ ] **Step 6: Commit**

Commit message: `refactor: 下线企业微信用户消息路径，保留群机器人 publisher`

---

## Task 4: 工厂指挥中心 7 屏回退数据源

**Files:**

- Modify: `backend/app/services/factory_command_service.py`
- Modify: `backend/app/schemas/factory_command.py`（如果需要加 `source: 'mes_projection' | 'local_shift_data'` 字段）
- Test: `backend/tests/test_factory_command_service.py`
- Test: `backend/tests/test_factory_command_routes.py`

- [ ] **Step 1: 写失败测试**

- `freshness.status='unconfigured'` 且 `mes_coil_snapshots` 表为空：`build_overview` 从 `ShiftProductionData`（当日 `data_status in ('confirmed','submitted')`）聚合出 `total_output / total_input / yield_rate / workshop_summary`，返回 `source='local_shift_data'`。
- `list_machine_lines` 在同样条件下按 `equipment_id` 聚合 `ShiftProductionData` 输出最近一次提交的机台。
- `list_coils` 在没有卷投影时返回空数组 + `source='local_shift_data'`（不伪造卷号）。
- freshness chip 新增 `source` 回传给前端。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py -q
```

- [ ] **Step 3: 实现回退聚合**

- 在 `factory_command_service` 顶部加一个 helper：`_projection_available(db) -> bool`，按 `db.query(MesCoilSnapshot).limit(1).first()` 检测当月至少一行；捕获 `ProgrammingError / OperationalError` 当作 False（投影迁移未跑时的兼容）。保留既有 fake-DB 路径（`hasattr(query, 'column_descriptions')` 分支）。
- `build_overview` / `list_workshops` / `list_machine_lines` 内部分叉：
  - 投影可用：保持现有逻辑。
  - 投影不可用：`_build_overview_from_shift_data(db, target_date)` 等回退函数，直接走 `ShiftProductionData` 的 SQL 聚合。
- 回退数据保证字段名与投影路径一致（前端无需改字段名），只增加 `source` 字段。

- [ ] **Step 4: 前端 freshness chip 展示数据源**

- `frontend/src/utils/factoryCommandFormatters.js`：`source='local_shift_data'` 显示为"手填口径"小标签（不是 error，不是 warning，只是灰色中性 chip）。
- `FactoryOverview.vue` 的 chip 组渲染用既有 token，不新增组件。

- [ ] **Step 5: GREEN + 浏览器验证**

```powershell
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py backend/tests/test_ai_context_service.py -q
npm --prefix frontend test -- frontend/tests/factoryCommandFormatters.test.js frontend/tests/factoryCommandScreens.test.js
npm --prefix frontend run build
```

浏览器核验：`MES_ADAPTER=null` 启动，`/manage/overview` 显示当日手填数据，chip 显示"未配置 · 手填口径"。

- [ ] **Step 6: Commit**

Commit message: `feat: 工厂指挥中心在 MES 投影空时回退手填口径`

---

## Rollback Plan

- Task 1 pytest 配置改动可回滚为 Git revert，不影响运行时。
- Task 2 readyz 降级若导致试点放量审计复杂化，可在 `.env` 设 `READINESS_STRICT_BINDING=true` 恢复旧硬拦。
- Task 3 企业微信删除不可逆，但回退只需 `git revert`；`.env` 中的 `WECOM_*` 字段保留未删除，群机器人 publisher 保留。
- Task 4 回退路径是 additive；若 SQL 聚合性能不达标，关闭 `_projection_available` 强制 False 即回到空数据态。

---

## Success Criteria

- [ ] `python -m pytest backend/tests -q` 全绿，无 collection error。
- [ ] `curl -k https://localhost/readyz` 在空绑定、空排班数据库上返回 200 + warnings。
- [ ] `grep -R "WECOM\|wecom" backend/app --include="*.py"` 仅剩 `group_bot` 与 `# deprecated` 注释。
- [ ] `MES_ADAPTER=null` 冷启动，`/manage/overview` 有当日手填数据 + "手填口径" chip。
- [ ] Phase 1 合入后，开 Phase 2 分支。

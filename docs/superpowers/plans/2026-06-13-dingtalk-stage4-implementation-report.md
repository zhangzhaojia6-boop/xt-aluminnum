# 2026-06-13 钉钉指定人员操作阶段四实施报告

## 1. 阶段结论

阶段四已完成本地服务闭环，可以标记完成。

本阶段完成的是“补产量、发布日报的安全门禁”，不是直接开放真实补产量或真实发布日报。现在系统已经能做到：只有白名单人员能发起操作，必须先生成预览，必须二次确认，未确认不能执行，执行默认 dry-run，不写正式生产数据。

## 2. 本阶段完成内容

- 新增 `backend/app/services/agent_operation_approval_service.py`
  - `request_operation_preview`：创建操作预览，只允许白名单人员发起。
  - `confirm_operation`：二次确认，只允许白名单审批人确认。
  - `execute_confirmed_operation`：执行门禁，默认 dry-run。
- 新增 `backend/tests/test_agent_operation_approval_service.py`
  - 覆盖普通人拦截、补产量预览、发布日报预览、未确认禁止执行、审批人校验、默认 dry-run。

## 3. 支持的操作类型

- `supplement_production`：补产量预览。
- `publish_daily_report`：发布日报预览。

注意：本阶段只建立审批和留痕，不直接写正式产量表，不直接发布日报。

## 4. 关键安全规则

- 普通人不能发起补产量或发布日报。
- 白名单人员发起后，只生成预览，不执行。
- 未二次确认前不能执行。
- 审批人也必须在白名单内。
- 执行默认是 `dry_run`，不会调用真实执行器。
- 真实执行必须显式传入执行器，并显式关闭 `dry_run`。
- 预览里强制写入：
  - `metric_write_allowed=false`
  - `report_publish_allowed=false`
  - `requires_confirmation=true`
- 每个操作有 `trace_id`，可追溯。

## 5. 为什么本阶段不直接改产量或发布日报

补产量和发布日报属于高风险写动作。若直接接正式数据表，风险主要有三类：

- 一句话误识别导致产量错写。
- 日报未经预览就发出，影响管理判断。
- 操作人、确认人、操作前后内容追不回来。

所以本阶段先做“门禁和留痕”。后续真正执行时，只需要把已有的业务写入函数作为执行器接进来，审批规则不用重写。

## 6. 验收证据

已执行测试：

```text
python -m pytest -q backend/tests/test_agent_operation_approval_service.py
结果：6 passed

python -m pytest -q backend/tests/test_agent_operation_approval_service.py backend/tests/test_agent_multimodal_evidence_service.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_sqlite_model_compatibility.py backend/tests/test_alembic_version_width.py backend/tests/test_migration_chain.py
结果：28 passed

python -m pytest -q backend/tests/test_dingtalk_service.py backend/tests/test_dingtalk_cli.py backend/tests/test_dingtalk_login_route.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_daily_report.py backend/tests/test_reporter_agent.py backend/tests/test_reminder_agent.py backend/tests/test_event_bus.py backend/tests/test_event_bus_persistence.py backend/tests/test_workflow_dispatcher.py backend/tests/test_ai_context_service.py
结果：78 passed
```

说明：

- 本阶段没有改前端页面，所以没有浏览器截图。
- 本阶段没有发真实钉钉消息。
- 本阶段没有改正式产量。
- 本阶段没有真实发布日报。

## 7. gstack 五视角 review

### CEO 视角：9.8

这一步把“以后可在钉钉补产量、发布日报”推进到可控状态。它能减少管理层等待和人工切系统，但没有冒险直接开放写动作。

未到满分原因：还没有接真实执行器和真实管理端审批页面。

### 工程师视角：9.8

实现小，复用阶段一的 `agent_operation_approvals` 表，不新增表。审批、确认、执行门禁分层清楚，后续接真实业务写入函数时风险低。

未到满分原因：真实执行器还没接入，暂时只完成门禁层。

### 设计师视角：9.8

阶段四已经把页面将来需要展示的字段定清楚：谁发起、谁确认、预览内容、执行状态、是否真实写入。后续管理端页面可以做成清晰的审批队列。

未到满分原因：审批页面还未实现。

### 安全审查视角：9.9

默认不写数据、不发布日报，且白名单、二次确认、dry-run、trace id 全部具备。真实执行必须显式传执行器，避免误触发。

未到满分原因：生产白名单还需要上线前和真实人员名单核对。

### 真实用户视角：9.8

指定人员以后可以少切系统，先看到预览再确认；普通人误操作不会造成生产数据变化。

未到满分原因：还没有钉钉卡片和管理端按钮让用户实际操作。

## 8. 阶段四是否可标记完成

可以标记完成。

完成口径：

- 指定人员白名单校验完成。
- 补产量预览完成。
- 发布日报预览完成。
- 二次确认完成。
- 未确认禁止执行。
- 默认 dry-run，不写正式数据。
- 阶段一到四和原有钉钉链路回归通过。

下一阶段建议：

- 接钉钉卡片确认入口。
- 管理端新增审批列表页。
- 上线前配置真实白名单。
- 接真实补产量执行器，但只写人工纠偏/补录表，不改 MES 原始数据。
- 接真实日报发布执行器，发布前必须比对预览内容。

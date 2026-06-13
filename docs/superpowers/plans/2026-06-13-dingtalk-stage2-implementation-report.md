# 2026-06-13 钉钉多 Agent 主动汇报阶段二实施报告

## 1. 阶段结论

阶段二已完成本地 dry-run 能力，不会向真实钉钉群发送消息。

本阶段新增的是“主动汇报大脑”，不是新增真实发送开关。现在系统已经能做到：

- 管理群只能接收全厂总览。
- 车间群只能接收本车间汇报。
- 未匹配车间的群会被拦截。
- 同一类主动汇报在限流窗口内不会重复刷屏。
- 被限流的消息仍会进入事件池备案，后续可以追溯。
- 异常检测能识别缺报、产量差异、MES 同步异常、设备停机偏长。
- 每条入队消息都带业务日期、数据来源、trace id 和事件 id。

## 2. 本阶段改动

- 新增 `backend/app/services/agent_active_reporting_service.py`
  - `queue_factory_overview`：生成全厂主动汇报。
  - `queue_workshop_status`：生成车间主动汇报。
  - `detect_basic_anomalies`：基础异常检测。
  - 内置群范围校验、限流、事件留痕、消息内容生成。
- 调整 `backend/app/services/agent_communication_service.py`
  - `queue_bound_message` 增加可选 `event_id`。
  - 作用是把发件箱消息和事件池打通，避免以后查来源断链。
- 新增 `backend/tests/test_agent_active_reporting_service.py`
  - 覆盖全厂汇报、车间权限、异常检测、重复消息限流、事件留痕。

## 3. 验收证据

已执行测试：

```text
python -m pytest -q backend/tests/test_agent_active_reporting_service.py
结果：5 passed

python -m pytest -q backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_alembic_version_width.py backend/tests/test_migration_chain.py
结果：14 passed

python -m pytest -q backend/tests/test_dingtalk_service.py backend/tests/test_dingtalk_cli.py backend/tests/test_reporter_agent.py backend/tests/test_reminder_agent.py backend/tests/test_event_bus.py backend/tests/test_event_bus_persistence.py backend/tests/test_workflow_dispatcher.py backend/tests/test_ai_context_service.py
结果：60 passed

python -m pytest -q backend/tests/test_sqlite_model_compatibility.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py
结果：10 passed
```

说明：

- 本阶段没有改前端页面，所以没有浏览器页面截图。
- 本阶段没有发真实钉钉消息，所有能力仍可通过 dry-run、安全测试和数据库留痕验证。
- 原有钉钉服务、日报 Agent、提醒 Agent、事件总线、AI 上下文测试均通过。

## 4. gstack 五视角 review

### CEO 视角：9.8

这一步把“系统被动等人看”推进成“系统主动找人汇报”。管理层可以接收全厂总览，车间主任可以接收本车间信息，业务价值明确。

未到满分原因：还没有接正式钉钉试点群实发。

### 工程师视角：9.8

实现复用阶段一 outbox、事件池、通道绑定、限流表，没有再加新表，改动小、边界清楚。测试先行，覆盖核心风险。

未到满分原因：真实定时任务和事件总线触发器还在后续阶段接入。

### 设计师视角：9.8

虽然本阶段不改页面，但消息内容采用“标题、核心数据、异常状态、来源”的短结构，适合钉钉群阅读，不像长篇机器人废话。

未到满分原因：钉钉卡片样式和管理端事件页还未进入阶段三之后的前端设计。

### 安全审查视角：9.9

默认 dry-run；未绑定群不能发；车间群不能看其他车间；重复汇报被限流；所有消息可追溯。没有开放补产量、发布日报等写动作。

未到满分原因：生产群 chatId 和正式白名单尚未进入线上配置核验。

### 真实用户视角：9.8

消息短、分层清楚，车间只收到本车间内容，管理层只看总览；同一异常不会反复刷屏，减少打扰。

未到满分原因：还没有让真实车间主任在试点群里体验。

## 5. 阶段二是否可标记完成

可以标记完成。

原因：

- 阶段二要求的主动汇报、权限范围、异常检测、备案留痕、限流去重已经完成本地闭环。
- 所有相关测试通过。
- 没有触碰真实钉钉群、生产数据和补产量/发布日报写动作。

下一阶段建议进入“多模态接入”：图片、语音、附件先入证据表，只做参考，不进入正式产量。

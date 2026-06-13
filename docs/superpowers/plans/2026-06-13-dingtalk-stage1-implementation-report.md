# 2026-06-13 钉钉多模态主动汇报阶段 1 施工报告

## 1. 本阶段目标

阶段 1 只做通讯底座，不发真实钉钉群，不开放补产量，不开放发布日报。

本阶段完成：

- Agent 配置表。
- 钉钉群/通道配置表。
- Agent 与通道绑定表。
- Agent 事件表。
- outbox 待发送消息表。
- 外部发送日志表。
- 多模态证据表。
- 操作审批表。
- 消息节流表。
- 最小服务层。
- 最小测试覆盖。

## 2. 代码变更

新增：

- `backend/app/models/agent_communication.py`
- `backend/app/services/agent_communication_service.py`
- `backend/alembic/versions/0040_agent_communication_outbox.py`
- `backend/tests/test_agent_communication_service.py`

修改：

- `backend/app/models/__init__.py`
- `backend/tests/test_migration_chain.py`

## 3. 已实现能力

- 可以注册 Agent。
- 可以注册钉钉群/通讯通道。
- 可以绑定 Agent 和群。
- 未绑定群会拒绝入队。
- 可以生成待发送 outbox 消息。
- dry-run 通道不会调用真实发送器。
- 非 dry-run 通道会调用注入的发送器。
- 每次发送结果会写入 `external_message_logs`。
- 消息带 `trace_id`、业务日期和来源说明。
- 同一异常窗口内可以限频，避免刷屏。

## 4. 明确未做

- 未发送真实钉钉消息。
- 未接正式生产群。
- 未开放补产量。
- 未开放发布日报。
- 未接图片/OCR/语音真实上传。
- 未做前端管理页。
- 未让 LLM 参与任何写动作。

## 5. 验证结果

已通过：

- `python -m pytest -q backend/tests/test_agent_communication_service.py backend/tests/test_sqlite_model_compatibility.py backend/tests/test_migration_chain.py`
- 结果：`9 passed`

已通过回归：

- `python -m pytest -q backend/tests/test_dingtalk_service.py backend/tests/test_dingtalk_cli.py backend/tests/test_reporter_agent.py backend/tests/test_reminder_agent.py backend/tests/test_event_bus.py backend/tests/test_event_bus_persistence.py backend/tests/test_workflow_dispatcher.py backend/tests/test_ai_context_service.py`
- 结果：`60 passed`

备注：

- 回归测试仍有 15 条历史 `datetime.utcnow()` 废弃警告，不是本阶段新增。

## 6. gstack 五视角复核

CEO 视角：9.7。

- 通讯底座先落地，后续主动汇报、异常检测、催办闭环有明确承载点。
- 没有急着发正式群，业务风险可控。

工程师视角：9.7。

- 新增模型和服务独立，不侵入现有日报、填报、MES 主链路。
- 有迁移、有 SQLite 兼容、有服务测试、有回归测试。

设计师视角：9.5。

- 本阶段还没做页面，但数据结构已经支持后续“Agent、通道、事件、消息、证据、审批”分区呈现。

安全审查视角：9.8。

- 默认 dry-run。
- 未绑定群拒绝。
- 发送日志留痕。
- 写动作仍未开放。
- 多模态证据和正式数据仍分离。

真实用户视角：9.6。

- 后续可实现“少打扰、准提醒、可追溯”的群汇报。
- 阶段 2 前还需要做管理端配置页面，否则普通管理员暂时不能可视化配置。

综合评分：9.66。

## 7. 下一阶段建议

进入阶段 2 前先做两个小步骤：

- 补 `/manage/agents`、`/manage/channels`、`/manage/agent-outbox` 的最小管理端入口，方便管理员不用改数据库。
- 做一个后端 dry-run API，允许管理员手动生成一条测试汇报，但仍不真实发正式群。

阶段 2 再做主动汇报 Agent，不建议直接跳到补产量和发布日报。

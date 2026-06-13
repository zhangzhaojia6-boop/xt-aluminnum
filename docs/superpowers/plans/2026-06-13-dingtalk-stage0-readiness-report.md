# 2026-06-13 钉钉多模态主动汇报阶段 0 检查报告

## 1. 本阶段范围

本阶段只做只读核对和 dry-run。

没有发送真实钉钉消息。
没有修改生产数据。
没有修改后端业务代码。

## 2. 已确认可复用能力

- 钉钉配置项已在后端保留。
- 钉钉个人工作通知方法已存在。
- 钉钉群消息方法已存在。
- `ReporterAgent` 可复用为日报主动汇报基础。
- `ReminderAgent` 可复用为缺报催办基础。
- `DatabaseEventBus` 可复用为主动汇报事件来源。
- `ai_context_service` 已有“先查事实，再让模型润色”的安全边界。

## 3. dry-run 结果

钉钉 dry-run 使用假配置执行，结果如下：

- 个人工作通知：通过，返回 `dingtalk_dry_run`。
- 群消息：通过，返回 `dingtalk_dry_run`。

结论：现有发送分支可以在不触发真实网络发送的情况下走通，适合阶段 1 继续扩展 outbox、群绑定和权限绑定。

## 4. 测试结果

已通过的测试：

- `backend/tests/test_dingtalk_service.py`
- `backend/tests/test_dingtalk_cli.py`
- `backend/tests/test_reporter_agent.py`
- `backend/tests/test_reminder_agent.py`
- `backend/tests/test_event_bus.py`
- `backend/tests/test_event_bus_persistence.py`
- `backend/tests/test_workflow_dispatcher.py`
- `backend/tests/test_ai_context_service.py`

结果：`60 passed`。

说明：有 15 条 `datetime.utcnow()` 废弃警告，不影响本次阶段 0 判断。

## 5. 当前阻塞

本地 readiness 检查未通过，原因是当前本地环境没有进入正式外部联通状态。

阻塞项：

- 数据库不可连接。
- `MES_ADAPTER=null`，外部 MES 数据源未启用。
- `WORKFLOW_ENABLED=false`，自动日报 workflow 未启用。
- `DINGTALK_ENABLED=false`，钉钉触达未启用。
- `APP_CONNECTION_ENABLED=false`，应用连接外发未启用。

这些阻塞是环境和配置问题，不是本轮新增代码导致。

## 6. 阶段 1 前置条件

进入正式阶段 1 前，需要满足：

- 本地或测试环境数据库可连接。
- 钉钉应用参数已配置到环境变量。
- `DINGTALK_NOTIFY_DRY_RUN=true` 用于第一轮测试。
- 至少有一个管理测试群。
- 至少有一个试点车间测试群。
- 管理层白名单已准备。
- 允许补产量和发布日报人员名单已准备，但阶段 1 暂不开放写动作。

## 7. 可以进入阶段 1 的范围

可以开始做：

- `agent_profiles`
- `communication_channels`
- `agent_channel_bindings`
- `agent_events`
- `agent_outbox`
- `agent_runs`
- `external_message_logs`
- `multimodal_evidence`
- `agent_rate_limits`

阶段 1 仍然只建议 dry-run，不建议直接接正式生产群。

## 8. 不建议现在做

- 不建议直接发正式生产群。
- 不建议开放补产量。
- 不建议开放发布日报。
- 不建议让图片/OCR/语音识别进入正式产量。
- 不建议让钉钉直接接触数据库。

## 9. 阶段 0 结论

阶段 0 通过“代码基础能力检查”和“dry-run 发送分支检查”。

阶段 0 未通过“正式联通 readiness”，原因是本地环境缺少数据库、MES、workflow、钉钉和外部连接正式配置。

建议下一步进入阶段 1 的本地开发：先做通讯底座和 outbox，并继续保持 dry-run。

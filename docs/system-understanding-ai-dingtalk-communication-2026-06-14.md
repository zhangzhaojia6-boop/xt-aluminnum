# 鑫泰铝业 数据中枢：AI 助手、钉钉与外部通讯链路理解

时间：2026-06-14 Asia/Shanghai

本记录是只读理解结果，用来防止后续丢上下文。没有修改生产数据，没有触发主动发送消息。

## 1. 一句话结论

当前系统已经有三层能力：

- 管理端 AI 助手：管理人员在 `/manage/ai-assistant` 或顶部抽屉里提问、看主动汇报、看关注列表。
- 钉钉 H5 免登：手机端可通过 `/api/v1/dingtalk/h5-login` 用钉钉身份换系统登录态，但前提是钉钉配置完整且系统账号已绑定钉钉用户。
- 外部通讯治理台：管理员在 `/manage/admin/agents` 看智能体、通道、事件、证据、审批、发件箱和知识口径。

重要边界：治理台能力已经上线，但线上当前 `agent_total=0`、`channel_total=0`，也就是还没有配置可真正外发的 agent 和通道。不要把“页面可用”误写成“已经能主动往钉钉群发生产日报”。

## 2. 前端入口

- `/manage/ai-assistant`：AI 工作台，组件是 `frontend/src/views/ai/AiWorkstation.vue`。
- 管理端顶部 `AI 助手` 按钮：常驻抽屉，组件是 `frontend/src/components/ai/AiAssistantDrawer.vue`。
- `/manage/admin/agents`：通讯治理台，组件是 `frontend/src/views/manage/admin/AgentManagementPage.vue`。
- `/review/brain`：旧入口，重定向到 `/manage/ai-assistant`。

导航和路由定义在 `frontend/src/router/index.js`，管理端外壳在 `frontend/src/layout/ManageShell.vue`。

## 3. 前端接口

- `frontend/src/api/ai-assistant.js`
  - `GET /ai/assistant/conversations`
  - `POST /ai/assistant/conversations`
  - `GET /ai/assistant/conversations/{id}/messages`
  - `POST /ai/assistant/conversations/{id}/messages`
  - `POST /ai/assistant/ask`
  - `GET /ai/runtime`
  - `GET /ai/briefings`
  - `POST /ai/briefings/generate-now`
  - `POST /assistant/actions`
  - `GET /ai/watchlist`
- `frontend/src/api/assistant.js`
  - `GET /assistant/capabilities`
  - `POST /assistant/query`
  - `POST /assistant/generate-image`
  - `GET /assistant/live-probe`
- `frontend/src/api/agent-management.js`
  - `GET /agent-management/overview`
  - `GET /agent-management/knowledge`
  - `POST /agent-management/knowledge/answer`
- `frontend/src/api/dingtalk.js`
  - `POST /dingtalk/h5-login`

只读 QA 时要分清“读页面”和“写记录”：

- 安全读取：`GET /ai/runtime`、`GET /ai/assistant/conversations`、`GET /ai/briefings`、`GET /ai/watchlist`、`GET /agent-management/overview`、`GET /agent-management/knowledge`。
- 会写系统记录：`POST /ai/assistant/conversations`、`POST /ai/assistant/conversations/{id}/messages`、`POST /ai/assistant/ask`、`POST /ai/briefings/generate-now`、`POST /ai/watchlist`、`POST /agent-management/knowledge/answer`。
- 会改变身份状态：`POST /dingtalk/h5-login` 会更新用户钉钉身份和 `last_login`。
- 可能触发业务处置：`POST /assistant/actions` 会按权限执行校验、催报、聚合或草稿提升，不能在生产环境随便点。
- 可能外发：发件箱真正外发只发生在通道非 `dry_run` 且执行发送时；配置和测试前必须先确认通道状态。

## 4. 后端入口

后端入口集中在 `backend/app/main.py`：

- `/api/v1/ai`：`backend/app/routers/ai.py`
- `/api/v1/assistant`：`backend/app/routers/assistant.py`
- `/api/v1/assistant/actions`：`backend/app/routers/assistant_actions.py`
- `/api/v1/agent-management`：`backend/app/routers/agent_management.py`
- `/api/v1/dingtalk`：`backend/app/routers/dingtalk.py`

权限边界：

- AI 工厂上下文要求管理员、管理者或审核类角色。
- 通讯治理台只允许管理员访问。
- AI 处置动作要求管理员或管理者，并会再按车间、班次、填报记录范围做权限判断。

## 5. 数据库表

AI 助手相关：

- `ai_conversations`：AI 对话。
- `ai_messages`：AI 消息。
- `ai_context_packs`：AI 上下文包。
- `ai_briefing_events`：主动汇报事件。
- `ai_watchlist_items`：关注列表。
- `assistant_usage`：LLM 调用用量记录。

外部通讯相关：

- `agent_profiles`：智能体档案。
- `communication_channels`：通讯通道，默认 `dry_run=True`。
- `agent_channel_bindings`：智能体和通道绑定。
- `agent_events`：智能体事件。
- `agent_outbox_messages`：待发送发件箱。
- `external_message_logs`：外部发送日志。
- `multimodal_evidence`：多模态证据留档。
- `agent_operation_approvals`：高风险操作审批。
- `agent_rate_limits`：主动汇报限频。

钉钉身份字段分布在 `users`、`employees`、`mobile_shift_reports` 和考勤相关表中。

## 6. AI 回答链路

`backend/app/services/ai_context_service.py` 是主链路：

- 从 `factory_command_service` 读取全厂状态、卷材、机列、同步新鲜度等上下文。
- 会按当前用户权限做范围过滤。
- 发送给 LLM 前会清理敏感字段，包含 `password`、`secret`、`token`、`credential`、`api_key` 等。
- 如果 LLM 没配置或超出每日限制，会走确定性回答，不会直接失败。
- 线上只读接口显示当前 `engine=grounded_llm`，`llm_configured=true`，`model_ref_set=true`。

## 7. 主动汇报链路

`backend/app/services/ai_briefing_service.py` 负责生成 AI 汇报：

- 每小时任务 `ai_hourly_briefing` 在 `backend/app/main.py` 注册。
- 汇报来源是 `factory_command_service` 和 `ai_rules_service`。
- 汇报会保存到 `ai_briefing_events`。
- 关注列表支持 quiet hours，静默时段会标记 `delivery_suppressed`。
- 建议动作只是建议，真正执行要走 `/assistant/actions` 和权限校验。

`backend/app/services/agent_active_reporting_service.py` 是外部主动报告队列：

- 全厂报告必须投到 `target_type=management` 的通道。
- 车间报告必须投到对应 `target_type=workshop` 且 `workshop_id` 匹配的通道。
- 会检测基础异常：缺报、产量差异、MES 同步异常、设备停机偏长。
- 会写入 `agent_events`，再写入 `agent_outbox_messages`。
- 有 `agent_rate_limits` 限频，防止同一业务日反复刷屏。

## 8. 外部发送安全边界

`backend/app/services/agent_communication_service.py` 是真正外发的闸门：

- 通道注册默认 `dry_run=True`。
- 如果通道是 dry-run，发件箱状态会变成 `dry_run`，并写入 `external_message_logs`，但不会真的调用外部发送。
- 只有通道非 dry-run 且类型是 `dingtalk_group` 时，才会调用 `dingtalk_service.send_group_message`。
- 治理台返回通道信息时会遮罩 `channel_key`，不直接暴露完整外部目标。

所以当前可理解为：系统已经具备“先入队、可审计、可干跑、再外发”的安全结构，但线上还没有配置真实 agent/channel。

## 8.1 前端治理台映射注意点

通讯治理台前端已经正确读取遮罩后的 `channel_key_masked`，不会把完整通道目标直接显示出来。

但有一个展示口径风险：后端主动汇报服务真实写入的事件类型是 `factory_overview_report`、`workshop_status_report`；前端当前翻译表里主要覆盖的是 `factory_overview`、`workshop_status`。一旦正式产生主动汇报事件，页面可能露出英文技术字段。这个不影响发送安全，但会影响管理端可读性，后续前端优化时应补齐中文映射。

## 9. 钉钉链路

`backend/app/services/dingtalk_service.py` 负责钉钉能力：

- `enabled` 需要 `DINGTALK_ENABLED=true` 且 CorpId、AppKey、AppSecret、AgentId 都有。
- `is_h5_configured` 需要 CorpId、AppKey、AppSecret。
- `h5-login` 会用钉钉 code 换 userid/unionid，再匹配系统用户。
- 如果未绑定、重复绑定或配置缺失，会返回明确错误。
- 发送群消息有速率限制，避免短时间高频外发。

配置项在 `backend/app/config.py`：

- `DINGTALK_*`
- `LLM_*`
- `APP_CONNECTION_*`
- `WORKFLOW_ENABLED`
- `AUTO_PUSH_ENABLED`

## 10. 线上只读验证

本次验证使用生产域名 `https://xtmijd.com`，只读访问为主：

- `POST /api/v1/auth/login`：成功，仅用于拿临时登录态。
- `GET /api/v1/ai/runtime`：成功，返回 LLM 已配置。
- `GET /api/v1/ai/assistant/conversations`：成功，返回 6 个会话。
- `GET /api/v1/ai/briefings`：成功，返回 0 条。
- `GET /api/v1/ai/watchlist`：成功，返回 0 条。
- `GET /api/v1/assistant/capabilities`：成功。
- `GET /api/v1/assistant/live-probe`：成功，但耗时约 20.9 秒，属于后续体验优化点。
- `GET /api/v1/agent-management/overview?limit=10`：成功，`safe_mode=true`，agent/channel/outbox 均为 0。
- `GET /api/v1/agent-management/knowledge`：成功，返回 11 条知识口径。

页面烟测：

- `/manage/ai-assistant`：可打开，显示 6 个对话；发现一次 `GET /api/v1/mes/supplement-readiness?limit=100 net::ERR_ABORTED`，当前像切页/请求中断噪声，需后续观察。
- `/manage/admin/agents`：可打开，无控制台错误；显示智能体 0、通道 0、知识口径 11。

## 11. 已有测试覆盖

后端已有测试文件：

- `test_ai_assistant_routes.py`
- `test_ai_briefing_service.py`
- `test_ai_context_service.py`
- `test_ai_rules_service.py`
- `test_assistant_routes.py`
- `test_assistant_actions_router.py`
- `test_assistant_action_service.py`
- `test_assistant_llm_integration.py`
- `test_agent_communication_service.py`
- `test_agent_active_reporting_service.py`
- `test_agent_management_router.py`
- `test_agent_management_overview_service.py`
- `test_agent_multimodal_evidence_service.py`
- `test_agent_operation_approval_service.py`
- `test_dingtalk_service.py`
- `test_dingtalk_h5_login.py`
- `test_dingtalk_login_route.py`
- `test_users_dingtalk_sync.py`

## 11.1 本轮定向验证

本轮只跑 AI、钉钉和外部通讯相关定向测试，不代表全站全量测试：

- 后端：`python -m pytest -q backend/tests/test_agent_communication_service.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_management_router.py backend/tests/test_agent_management_overview_service.py backend/tests/test_agent_multimodal_evidence_service.py backend/tests/test_agent_operation_approval_service.py backend/tests/test_agent_knowledge_service.py backend/tests/test_ai_context_service.py backend/tests/test_ai_briefing_service.py backend/tests/test_ai_briefing_actions.py backend/tests/test_ai_assistant_routes.py backend/tests/test_assistant_actions_router.py backend/tests/test_assistant_action_service.py backend/tests/test_assistant_llm_integration.py backend/tests/test_dingtalk_service.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_login_route.py`
- 结果：`93 passed, 2 warnings`。两个 warning 都是测试里的 `datetime.utcnow()` 弃用提醒，不是当前业务失败。
- 前端：`node --test tests/agentManagementPage.test.js tests/aiAssistantContracts.test.js tests/aiAssistantUiContract.test.js tests/aiWorkstationActions.test.js tests/assistantFallbackTruthfulness.test.js tests/dingtalkAutoLogin.test.js tests/userDingtalkSync.test.js`
- 结果：`29 passed`。

## 12. 当前风险和后续建议

- `/assistant/live-probe` 会真实探测外部模型能力，线上可用但偏慢，不适合在页面加载时频繁触发。
- 通讯治理台没有配置 agent/channel，所以还不能真实主动往钉钉群发消息。
- 外部通讯正式开通前，需要先建立：agent、channel、binding、dry-run 试运行、审批规则、限频规则、发送失败重试策略。
- 生产环境 QA 不应随便调用 `/ai/briefings/generate-now`、`/assistant/actions`、`/agent-management/knowledge/answer`，除非明确是在测试库或指定可写场景。
- AI 工作台的 `ERR_ABORTED` 需要后续区分是普通请求取消，还是某个组件不该在 AI 页触发 MES 辅助填报接口。

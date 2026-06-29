# 鑫泰铝业智能大脑 20 问真实验收报告

日期：2026-06-29
计划：`docs/superpowers/plans/2026-06-28-hermes-20-question-real-acceptance-plan.md`

## 结论

本轮完成了 20 问验收框架、runner、真实钉钉送达门禁、CLI、安全报告路径、数据中枢删除守卫和管理端可见性检查。

当前结论分两层：

| 项目 | 结果 | 说明 |
|---|---|---|
| 后端聚焦门禁 | 通过 | 76 个相关测试通过 |
| 管理端 trace/outbox/logs 可见性 | 通过 | 701 个前端契约测试通过，页面已有 `trace_id`、outbox 和外发日志 |
| 数据中枢删除守卫 | 通过 | 守卫只检查不删除；TS/TSX 运行时引用、测试引用误拦截和文本 references 已覆盖 |
| 真实钉钉 20 问外发 | 未执行 | 批准目标 `dingtalk_group:test-group`、`dingtalk_work_notice:dt-person-001` 当前未在 `communication_channels` 中配置 |
| 删除旧文件 | 未执行 | 本轮没有明确删除候选；登记表中只有 protect/freeze 项 |

## 后端门禁

命令：

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_real_acceptance.py tests/test_hermes_20_question_runner.py tests/test_hermes_real_dingtalk_delivery_gate.py tests/test_datahub_deletion_guard.py tests/test_hermes_mes_read_service.py tests/test_hermes_root_owner_production_orchestrator.py tests/test_hermes_fact_priority_service.py tests/test_dingtalk_agent_inbound_route.py
```

结果：

```text
76 passed in 10.08s
```

覆盖内容：

- 20 问目录和四层评分。
- `鑫泰铝业智能大脑` 中文身份和 `追踪编号`。
- RAG 不可作为实时事实来源。
- DingTalk/MES/WMS/数据中枢投影来源链路检查。
- 真实送达分类：`sent`、`dry_run`、环境失败、代码异常。
- runner 从 `AgentRun`、outbox、外发日志构造验收快照。
- approved DingTalk targets 只走 `agent_communication_service`，不裸调钉钉发送服务。
- MES 只读读取链路相关回归。
- 钉钉入口和事实优先级相关回归。

## 真实钉钉预检

只读查询了数据库中的批准目标配置：

```text
dingtalk_group:test-group missing
dingtalk_work_notice:dt-person-001 missing
user:1 username=ZR2-3 dingtalk_user_id=None
```

因此没有执行：

```powershell
cd backend
python scripts/hermes_20_question_acceptance.py --business-date 2026-06-27 --sender-external-id dt-root-001 --target dingtalk_group:test-group --target dingtalk_work_notice:dt-person-001 --real-delivery
```

原因很简单：当前目标是占位名，不是已确认的真实非 dry-run 钉钉通道。如果直接运行，runner 会尝试注册非 dry-run 通道并外发到这些占位 key，这不符合“先确认批准目标已配置”的门禁。

解锁真实外发验收需要先完成：

1. 在 `communication_channels` 中配置真实测试群通道，`channel_type=dingtalk_group`，`channel_key=<真实测试群 key>`，`dry_run=False`，`is_active=True`。
2. 在 `communication_channels` 中配置真实个人工作通知通道，`channel_type=dingtalk_work_notice`，`channel_key=<真实钉钉用户 id>`，`dry_run=False`，`is_active=True`。
3. 确认 `--sender-external-id` 使用真实 root owner 钉钉用户 id。
4. 使用真实通道 key 替换计划里的占位值后再运行 CLI。

## 数据中枢删除守卫

本轮新增并验证了删除前守卫：

```powershell
cd backend
python scripts/check_datahub_deletion_guard.py path/to/candidate.py --json
```

守卫规则：

- Hermes、MES/WMS、DingTalk、审计、RAG、入口和大仪表盘相关路径直接阻断。
- 被 Python/JS/TS/TSX/Vue 运行时代码引用的候选直接阻断。
- 只被测试文件引用不作为运行时阻断。
- 默认文本输出会列出引用文件。
- 不执行删除动作。

本轮没有明确删除候选，因此没有删除文件，也没有更新 `docs/datahub-deprecation-register.md`。

## 管理端可见性

命令：

```powershell
cd frontend
npm run test -- --run tests/agentManagementPage.test.js tests/channelManagementPage.test.js tests/aiAssistantUiContract.test.js
```

结果：

```text
701 passed
```

搜索确认：

- `AgentManagementPage.vue` 已展示 `trace_id`。
- 页面已有 outbox 列表。
- 页面已有外发日志区块。
- API 已提供 `/agent-management/outbox/${outboxMessageId}/logs`。

因此 Task 6 没有改前端业务代码。

## 当前状态

可以说已经完成的是：软件侧验收门禁和删除保护已经搭起来，并通过了聚焦测试。

不能说已经完成的是：真实钉钉 20 问外发 18/20 以上通过。它还缺真实、已批准、非 dry-run 的测试群和个人通道配置。

下一步应该先做一件小事：把真实测试群和个人钉钉通道配置好，然后用同一个 CLI 跑一次真正的 20 问外发验收。

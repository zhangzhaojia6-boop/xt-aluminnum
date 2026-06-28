# Hermes root_owner 私聊生产 smoke

日期：2026-06-28

## 运行方式

- 本地 API：`http://127.0.0.1:8765`
- 数据库：临时 sqlite smoke 数据库
- 钉钉发送：`DINGTALK_NOTIFY_DRY_RUN=true`
- 入站脚本：`backend/scripts/run_hermes_root_owner_private_smoke.py`

这次 smoke 验证的是真实 HTTP 路由、root_owner 私聊识别、trace、outbox 和 external log。它没有真实外发钉钉消息。

## 问题

- 今天咋样

## 结果

| 问题 | trace_id | 状态 | 回复状态 | 最高事实源 |
|---|---|---|---|---|
| 今天咋样 | root-owner-smoke-local-20260628-001 | answered | sent / dingtalk_dry_run | 未命中；缺 `dingtalk_group_content`、`mes_readonly` |

## 数据库证据

| 表 | 结果 |
|---|---|
| `chat_inbox` | 1 条 `dingtalk_private`，sender 为 `dt-root-smoke-001` |
| `agent_runs` | 1 条 `factory_dispatch`，状态 `answered` |
| `agent_outbox_messages` | 1 条，状态 `sent`，`attempts=1` |
| `external_message_logs` | 1 条 `dingtalk_work_notice`，状态 `sent`，detail 为 `dingtalk_dry_run` |

## 结论

root_owner 钉钉私聊本地 production-like 链路已跑通：入站、Hermes 生产闭环、trace、outbox、external log 都有记录。

下一次要做真实生产 smoke 时，需要配置真实 `HERMES_SMOKE_BASE_URL`、入站 token 和 root_owner 钉钉 user id，并让钉钉发送从 dry-run 切到真实发送。

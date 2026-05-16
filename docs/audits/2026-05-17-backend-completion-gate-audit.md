# 2026-05-17 后端完全体完成门禁审计

## 结论

`docs/superpowers/plans/2026-05-16-backend-completion.md` 的代码、迁移、测试、CI、MES readiness 和本地可观测性门禁已经具备当前证据；但后端完全体目标仍不能标记完成，也不能调用 goal complete。

阻塞项只剩真实外部验收：

- 钉钉工作通知必须送达一个真实绑定的 `dingtalk_user_id`。
- AI 助手必须在生产等价环境返回真实 LLM 回答。
- 生产正式验收前还要先把 `codex/gai` 最新 HEAD 合并/部署到目标环境，否则生产 `main@ed4a7b2` 不包含 `check_llm_live.py` 和 `dingtalk_cli.py send-test`。

## 当前已证明

| 完成标志 | 当前判断 | 证据 |
| --- | --- | --- |
| `alembic upgrade head` 从空库建表成功 | 已证明 | Windows 临时 SQLite 执行 `python -m alembic upgrade head` 后再跑 `python scripts/seed_production.py`，二者 exit 0 |
| MES 适配器对接真实系统 | 已证明 | 生产 `/readyz` 返回 `status=ready`，`mes_sync.configured=true`，最近 `last_run_status=success`、`fetched_count=50`、`upserted_count=50`；实时聚合只读探针 `live_aggregation_data_source=mixed` |
| 定时任务 4 个 job 运行正常 | 已证明到代码层 | `tests/test_scheduler.py` 覆盖 `daily_report`、`mes_sync`、`fill_reminder`、`data_archive` 四个 job；生产 `/readyz` 当前 `schedule=ok` |
| `/health` 端点返回 200 | 已证明到分支代码层 | `tests/test_health.py` 覆盖 `/health`、`/healthz`、`/readyz`；公网 `/healthz` 返回 `status=ok` |
| refresh token 流程通 | 已证明 | `tests/test_auth_routes.py` 与 refresh token 相关测试在后端全量中通过 |
| CI pipeline 全绿 | 已证明 | `codex/gai` 最新 HEAD 的 GitHub Actions `frontend-build`、`backend-tests`、`compose-smoke`、`deploy-staging` 全部 success |
| 829+ 测试全绿 | 已证明 | Windows 后端全量 `942 passed, 3 skipped, 124 deselected`；WSL/Python 3.12 后端全量 `942 passed, 3 skipped, 124 deselected` |

## 当前仍未证明

| 完成标志 | 当前状态 | 不能打勾的原因 | 需要的最终证据 |
| --- | --- | --- | --- |
| 钉钉推送真实送达 | 阻塞 | 生产钉钉 token 可取到，但 `contacts --department-id 1 --json` 返回 `missing_scope=qyapi_get_department_member`；生产 active 用户/员工绑定 `dingtalk_user_id` 数为 0 | 开通钉钉通讯录权限，绑定一个真实 active `dingtalk_user_id`，再运行 `python scripts/dingtalk_cli.py send-test --userid <real_dingtalk_user_id> --json`，返回 `ok=true` |
| AI 助手返回真实 LLM 回答 | 阻塞 | 服务器 `backend/.env` 没有 LLM 配置；根 `.env` 的 `LLM_API_KEY` 为空；`python scripts/check_llm_live.py --json` 在未配置时只能返回 `configured=false` | 在生产等价环境配置 `LLM_ENABLED=true`、`LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL` 或 `LLM_ENDPOINT_ID`，再运行 `python scripts/check_llm_live.py --json`，返回 `ok=true`、`response_received=true` |

## 最终验收命令

先合并/部署 `codex/gai` 最新 HEAD 到目标环境，再在目标环境执行：

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=. .venv/bin/python scripts/check_statistics_module_ready.py --json --check-live-aggregation --check-dingtalk-contacts
PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py token --json
PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py contacts --department-id 1 --json
PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py send-test --userid <real_dingtalk_user_id> --json
PYTHONPATH=. .venv/bin/python scripts/check_llm_live.py --json
```

完成条件：

- readiness 不再出现 `LLM_DISABLED`、`APP_CONNECTION_DISABLED`、`DINGTALK_NO_BOUND_USERS`、`DINGTALK_CONTACTS_PERMISSION_MISSING`。
- 钉钉 token、通讯录权限、真实人员绑定和 `send-test` 均通过。
- LLM live check 返回真实响应。
- `/readyz` 仍为 `status=ready`，MES sync 仍为 configured 且最近同步成功。

在上述证据出现前，本目标必须保持 active。

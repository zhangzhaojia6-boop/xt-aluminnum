# 2026-05-17 后端完全体完成门禁审计

## 结论

`docs/superpowers/plans/2026-05-16-backend-completion.md` 的代码、迁移、测试、CI、MES readiness、生产 LLM live check、钉钉 token 和钉钉真实工作通知送达均已具备当前证据。最新生产环境已经部署 `main@a57af67`，最终聚合门禁命令 `PYTHONPATH=. .venv/bin/python scripts/check_backend_completion_gate.py --json --dingtalk-userid admin` 返回 `ok=true` 且 exit 0。

仍需作为运营后续项跟踪，但不再阻塞本计划完成门禁：

- `APP_CONNECTION_ENABLED=false`，统计模块对外推送连接面仍未启用；该项需要外部系统的 `APP_CONNECTION_API_BASE` / `APP_CONNECTION_API_KEY` 后再开启。
- 钉钉 readiness 仍保留 `DINGTALK_NO_BOUND_USERS` 与 `DINGTALK_CONTACTS_PERMISSION_MISSING` warning，通讯录成员读取权限仍缺 `missing_scope=qyapi_get_department_member`，生产库 `users`、`employees` 的 `dingtalk_user_id` 非空数量均为 0；本次用钉钉 userid `admin` 完成了真实送达门禁，但后续试点人员 UAT 仍应同步通讯录并绑定真实人员。

## 当前已证明

| 完成标志 | 当前判断 | 证据 |
| --- | --- | --- |
| `alembic upgrade head` 从空库建表成功 | 已证明 | Windows 临时 SQLite 执行 `python -m alembic upgrade head` 后再跑 `python scripts/seed_production.py`，二者 exit 0 |
| MES 适配器对接真实系统 | 已证明 | 生产 `/readyz` 返回 `status=ready`，`mes_sync.configured=true`，最近 `last_run_status=success`、`fetched_count=50`、`upserted_count=50`；实时聚合只读探针 `live_aggregation_data_source=mixed` |
| 定时任务 4 个 job 运行正常 | 已证明到代码层 | `tests/test_scheduler.py` 覆盖 `daily_report`、`mes_sync`、`fill_reminder`、`data_archive` 四个 job；生产 `/readyz` 当前 `schedule=ok` |
| `/health` 端点返回 200 | 已证明到分支代码层 | `tests/test_health.py` 覆盖 `/health`、`/healthz`、`/readyz`；公网 `/healthz` 返回 `status=ok` |
| refresh token 流程通 | 已证明 | `tests/test_auth_routes.py` 与 refresh token 相关测试在后端全量中通过 |
| AI 助手返回真实 LLM 回答 | 已证明 | 生产 `PYTHONPATH=. .venv/bin/python scripts/check_llm_live.py --json` 返回 `ok=true`、`response_received=true`，内容为 `DATA_HUB_LLM_OK` |
| 钉钉推送真实送达 | 已证明 | 生产 `PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py send-test --userid admin --message '数据中枢后端门禁联通测试' --json` 返回 `ok=true`、`detail=dingtalk_sent` |
| 后端完成聚合门禁 | 已证明 | 生产 `PYTHONPATH=. .venv/bin/python scripts/check_backend_completion_gate.py --json --dingtalk-userid admin` 返回 `ok=true`、`blockers=[]` |
| CI pipeline 全绿 | 已证明 | `main@a57af67` 的 GitHub Actions `frontend-build`、`backend-tests`、`compose-smoke` 全部 success；`codex/gai@a57af67` 的 Deploy Staging success |
| 829+ 测试全绿 | 已证明 | Windows 后端全量 `947 passed, 3 skipped, 124 deselected`；WSL/Python 3.12 后端全量 `947 passed, 3 skipped, 124 deselected` |

## 运营后续项

| 项目 | 当前状态 | 影响 | 后续证据 |
| --- | --- | --- | --- |
| 应用连接外发 | `APP_CONNECTION_DISABLED` | 统计模块不能对外推送到尚未提供的外部系统 | 配置 `APP_CONNECTION_API_BASE` / `APP_CONNECTION_API_KEY` 后，`check_statistics_module_ready.py --json --check-live-aggregation --check-dingtalk-contacts` 不再返回该 hard issue |
| 钉钉通讯录同步 | 缺 `qyapi_get_department_member` | 不能自动读取通讯录并给试点用户绑定 `dingtalk_user_id` | 钉钉开放平台开通权限后，`scripts/dingtalk_cli.py contacts --department-id 1 --json` 返回 `ok=true` |
| 试点人员绑定 | active 用户/员工绑定数为 0 | 管理员 userid 可送达，但普通试点人员仍需 UAT 绑定 | 同步通讯录或人工绑定后，生产 readiness 显示 active DingTalk binding count > 0 |

## 最终验收命令

目标环境已部署 `main@a57af67`。最终门禁命令为：

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=. .venv/bin/python scripts/check_statistics_module_ready.py --json --check-live-aggregation --check-dingtalk-contacts
PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py token --json
PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py contacts --department-id 1 --json
PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py send-test --userid admin --json
PYTHONPATH=. .venv/bin/python scripts/check_llm_live.py --json
PYTHONPATH=. .venv/bin/python scripts/check_backend_completion_gate.py --json --dingtalk-userid admin
```

完成条件：

- 计划内 readiness 不再出现 `MES_UNCONFIGURED`、`WORKFLOW_DISABLED`、`DINGTALK_DISABLED`。
- 钉钉 token 和 `send-test` 均通过。
- LLM live check 返回真实响应。
- 后端完成聚合门禁返回 `ok=true` 且 exit 0。
- `/readyz` 仍为 `status=ready`，MES sync 仍为 configured 且最近同步成功。

上述计划内证据已经出现；后续只保留应用连接外发、钉钉通讯录权限和试点人员绑定为运营类跟进项。

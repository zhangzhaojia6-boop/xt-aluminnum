# Daily Report Fact Closure Smoke

日期：2026-07-02

目标：验证最近 3 个已完成业务日能否用真实数据库生成 `DailyFactBundle`，并与 `D:\输出skill` 锁定日报文本做字段级对齐。

## Command Used

本地执行：

```powershell
py -3 backend\scripts\check_daily_report_output_skill_alignment.py --days 3 --output-skill-root "D:\输出skill" --artifact-dir docs\superpowers\reports\daily-report-fact-closure-local --full-differences --json
```

说明：实施计划里的 `--recent-business-days` 是旧参数名，当前脚本实际参数为 `--days`。

生成 artifact：

- `docs/superpowers/reports/daily-report-fact-closure-local/daily_report_alignment.json`
- `docs/superpowers/reports/daily-report-fact-closure-local/daily_report_alignment.md`

## Database Target

本地脚本读取当前后端环境配置，密钥未输出。

结果显示当前本地数据库目标为 `localhost:5432`，但 PostgreSQL 未启动或未监听，连接被拒绝。脚本没有崩溃，而是为每个业务日生成了 `status=error` 的可读失败行。

## Output Skill Root

`D:\输出skill`

本地路径存在，已被脚本接受为参考目录。

## Business Dates Tested

| Business date | Status | Field match rate | Exact match | Action |
|---|---|---:|---|---|
| 2026-06-29 | error | - | false | inspect_error_and_rerun |
| 2026-06-30 | error | - | false | inspect_error_and_rerun |
| 2026-07-01 | error | - | false | inspect_error_and_rerun |

## Five Critical Fields

本地数据库连接失败，未能生成 `DailyFactBundle`，因此 5 个关键字段没有进入字段级比对：

- `total_output_daily`
- `finished_inbound_daily`
- `wip_total`
- `total_electricity_kwh`
- `daily_yield_rate`

当前结论不是“字段失败”，而是“事实包构建前置数据库连接失败”。

## MES/WMS Read Health

本地 smoke 未进入 MES/WMS 读取阶段，因为 PostgreSQL 事实包构建前置连接失败。

生产公网健康探测：

```text
https://xtmijd.com/api/v1/healthz -> 200
https://xtmijd.com/api/v1/readyz  -> 200
```

这只能证明生产 HTTP 健康接口可达，不能替代生产日报字段对齐 smoke。

## DingTalk Evidence Count

本地 smoke 未进入事实包构建阶段，因此没有读取到钉钉证据计数。

## Missing Fields By Owner Action

当前失败分组：

| Group | Fields | Owner action |
|---|---|---|
| local_database_unavailable | all critical fields pending | 启动本地 PostgreSQL 或切换到生产数据库只读环境后重跑 |

## Production Smoke

尝试使用仓库历史云机入口执行只读生产命令：

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 root@8.140.218.13 "cd /srv/aluminum-bypass && pwd && git rev-parse --abbrev-ref HEAD && git rev-parse --short HEAD"
ssh -o BatchMode=yes -o ConnectTimeout=8 root@xtmijd.com "cd /srv/aluminum-bypass && pwd && git rev-parse --short HEAD"
```

结果：

```text
Connection closed by 8.140.218.13 port 22
Connection closed by 198.18.0.12 port 22
```

因此本轮没有完成生产机 shell 内的日报对齐 smoke。不能写成“生产 smoke 已通过”。

生产机可执行命令保持为：

```bash
python backend/scripts/check_daily_report_output_skill_alignment.py --days 3 --output-skill-root "/tmp/output-skill" --artifact-dir docs/superpowers/reports/daily-report-fact-closure-production --full-differences --json
```

## Next Highest-Leverage Fixes

1. 在本机启动或配置正确 PostgreSQL，再重跑本地 smoke，确认 artifact 从 `status=error` 进入字段级差异。
2. 恢复可用的生产 SSH 通道，或在生产机控制台直接执行生产 smoke 命令。
3. 将 `D:\输出skill` 同步或挂载到生产机 `/tmp/output-skill`，避免生产 smoke 缺参考源。
4. 生产 smoke 通过后，按 5 个关键字段逐项看 `fact_closure.status/source/trace_id/action`。

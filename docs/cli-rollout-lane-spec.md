# CLI / Scripts / Rollout Lane Spec

> 日期：2026-04-06
> 目的：把当前仓库里的命令、脚本、放量门槛统一分成 dev / trial / ops / rollback 四层，并给出“local runnable / can trial / formal-use”三档标准与当前证据映射。

## 1. 三档标准

### A. local runnable
定义：
- 在当前代码库和本地环境里可直接执行；
- 失败时能给出确定性错误；
- 不要求现场放量条件已经满足。

最低证据：
- `--help` 可用，或
- 定向 pytest 通过，或
- 本地 compose / curl 能返回结构化结果。

### B. can trial
定义：
- 已经连接到实际运行栈（本地 compose / 试点库）；
- 输出足以用于试点排查、值班复盘或预检；
- 允许发现阻断问题，但不允许把“阻断”误判成“可正式上线”。

最低证据：
- live `/readyz`、`check_pilot_*`、`check_wecom_*` 之类命令可以实际跑通；
- 输出包含明确 pass / block / warning / error 语义。

### C. formal-use
定义：
- 可作为正式试点放量或运维动作的依据；
- 不只要求命令“能跑”，还要求 readyz / Gate A/B/C / 回滚预案同时成立。

最低证据：
1. live `/readyz` 返回 200 且 `status=ready`；
2. `docs/pilot-readiness-checklist.md` 的 Gate A / B / C 留痕通过；
3. 降级与回滚命令已明确；
4. 如果涉及数据变更，先有备份。

## 2. 当前证据快照（2026-04-06）

### 已验证证据
- `curl -k https://localhost/healthz` → **200 OK**。
- `curl -k https://localhost/readyz` → **503**，`pipeline=blocked`。
- `docker compose ps` 显示 `db` / `backend` / `nginx` 均为运行态，且 `backend` 为 `healthy`。
- `docker compose exec -T backend sh -lc 'cd /app && pytest tests/test_health.py tests/test_config_readiness_service.py -q'` → **9 passed**。
- `docker compose exec -T backend sh -lc 'cd /app && python scripts/check_pilot_config.py --date 2026-04-06 --json'` → `hard_gate_passed=false`。
- `docker compose exec -T backend sh -lc 'cd /app && python scripts/check_pilot_metrics.py --date 2026-04-06 --json'` 可执行，返回 `reporting_rate=0.0` 且提示“应报清单为空”。
- `docker compose exec -T backend sh -lc 'cd /app && python scripts/check_pilot_anomalies.py --date 2026-04-06 --json'` 可执行，当前返回 0 条异常。
- `check_wecom_account_mapping.py --help`、`check_pilot_config.py --help`、`check_pilot_metrics.py --help`、`check_pilot_anomalies.py --help` 均可执行。
- `docker compose exec -T backend sh -lc 'cd /app && pytest tests/test_runtime_config.py tests/test_generate_env_script.py -q'` 当前 **1 failed / 8 passed**；失败原因是容器内缺少根目录 `/scripts/generate_env.py`。
- `docker compose run --rm backend sh -lc 'pytest -q'` 当前 **5 failed / 238 passed**；其中 4 个失败都指向 backend 镜像看不到仓库根目录文件，另 1 个失败为 `test_alembic_version_width.py` 断言当前版本目录里应存在长度 >32 的 revision id。
- `cd frontend && npm run build` → **passed**。

### 当前阻断
live `/readyz` 与 `check_pilot_config.py --date 2026-04-06 --json` 一致显示以下硬阻断：
- `EQUIPMENT_USER_BINDING_INVALID`
- `SCHEDULE_EMPTY`

这意味着：**当前环境可 trial，不可 formal-use。**

### 关键解释
`docker compose` 的容器健康检查现在探测的是 `/healthz`，不是 `/readyz`。因此：
- `backend=healthy` 只代表“服务活着”；
- **不代表** “已通过试点放量门槛”；
- 放量必须以 `/readyz` 和 Gate A/B/C 为准。

## 3. 命令 / 脚本分层

| 层级 | 命令/脚本 | 用途 | 当前标准 | 备注 |
|---|---|---|---|---|
| dev | `docker compose up -d --build` | 本地拉起整套栈 | local runnable | 已有 live 栈在跑 |
| dev | `docker compose ps` | 看服务状态 | local runnable | 只能证明进程/容器状态 |
| dev | `curl -k https://localhost/healthz` | 活性检查 | local runnable | 当前 200 |
| dev | `docker compose exec -T backend ... pytest tests/test_health.py tests/test_config_readiness_service.py -q` | 验证 readyz 语义与配置门禁 | local runnable | 当前 9 passed |
| dev | `scripts/generate_env.py` | 生成根目录 `.env` 模板 | host-only local runnable | 是根目录脚本，不属于 backend 镜像内脚本 |
| dev | `cd frontend && npm run build` | 前端构建验证 | local runnable | 2026-04-06 已通过 |
| trial | `curl -k https://localhost/readyz` | 现场前 readiness 总闸门 | can trial | 当前 503 blocked |
| trial | `python scripts/check_pilot_config.py --date <日期> --json` | Gate A 配置预检 | can trial | 当前 hard gate 未通过 |
| trial | `python scripts/check_pilot_metrics.py --date <日期> --json` | 每日试点复盘 | can trial | 当前可跑，但无应报数据 |
| trial | `python scripts/check_pilot_anomalies.py --date <日期> --json` | 每日异常复盘 | can trial | 当前可跑，0 异常 |
| trial | `python scripts/check_wecom_account_mapping.py --input <文件> --json` | 账号映射清单预检 | can trial | 本次仅验证了 `--help` |
| trial | `docs/pilot-readiness-checklist.md` 三个 Gate 命令 | 试点前预检留痕 | can trial → formal-use 入口 | 当前只拿到 Gate A 的部分证据 |
| ops | `docker compose exec backend alembic upgrade head` | 正式环境 DB 迁移 | formal-use | 需备份后执行 |
| ops | `python scripts/init_master_data.py` | 初始化基础主数据 | formal-use | backend 容器启动命令已串联 |
| ops | `python scripts/init_real_master_data.py` | 初始化真实主数据 | formal-use | backend 容器启动命令已串联 |
| ops | `python scripts/create_admin.py` | 初始化/修复管理员账号 | formal-use | 会改库 |
| ops | `docker compose -f docker-compose.yml -f docker-compose.prod.yml config/up` | 生产覆盖验证/拉起 | formal-use | README 已列出；不属于日常试点排查 |
| rollback | `AUTO_PUBLISH_ENABLED=false` | 停自动发布 | formal-use rollback | 保留填报/校验/汇总 |
| rollback | `AUTO_PUSH_ENABLED=false` | 停消息推送 | formal-use rollback | 保留业务链路留痕 |
| rollback | `WORKFLOW_ENABLED=false` / `WECOM_BOT_ENABLED=false` / `WECOM_APP_ENABLED=false` | 停工作流触达 | formal-use rollback | `docs/workflow-rollout.md` 已定义 |
| rollback | `scripts/backup_db.sh` / `.ps1` | 回滚前备份 | formal-use rollback | 应先于迁移/正式放量 |
| rollback | `scripts/restore_db.sh` / `.ps1` | 数据库恢复 | formal-use rollback | 属于强回滚动作 |

## 4. 当前证据映射到三档标准

| 对象 | local runnable | can trial | formal-use | 结论 |
|---|---|---|---|---|
| `/healthz` | 是 | 否 | 否 | 只能证明服务活着 |
| `/readyz` | 是 | 是 | 否 | 当前 503 blocked |
| Gate A 定向 pytest | 是 | 是 | 否 | 语义测试通过，但 live gate 未过 |
| `check_pilot_config.py` | 是 | 是 | 否 | 当前明确阻断放量 |
| `check_pilot_metrics.py` | 是 | 是 | 否 | 当前无试点样本数据 |
| `check_pilot_anomalies.py` | 是 | 是 | 否 | 当前无异常，不代表可放量 |
| `check_wecom_account_mapping.py` | 是（help） | 待补清单实跑 | 否 | 需要现场账号清单 |
| `scripts/generate_env.py` | 是（host） | 不直接作为 trial gate | 否 | 是 bootstrap 工具，不是放量证据 |
| backup / restore | 否（不建议日常试跑） | 否 | 是 | 属于正式运维/回滚命令 |

## 5. 当前结论

截至 **2026-04-06**：
- 该仓库的 CLI / scripts 体系已经具备 **dev + trial + rollback** 基础骨架；
- **formal-use 仍未满足**，因为 live readiness 已明确返回 `503 not_ready`；
- 当前最重要的放量前动作不是“继续拉环境”，而是先清掉：
  1. `EQUIPMENT_USER_BINDING_INVALID`
  2. `SCHEDULE_EMPTY`

只有在这两个硬阻断清零后，才值得继续补 Gate B / Gate C 的正式留痕。

## 6. 一个需要特别注意的执行边界

`tests/test_generate_env_script.py`、`tests/test_nginx_https_config.py`、`tests/test_real_master_data.py`、`tests/test_rebranding.py` 都会读取仓库根目录文件；但 backend Docker 镜像的 build context 是 `./backend`，容器内只有 `/app` 内容，看不到这些根目录路径。因此：
- `scripts/generate_env.py`、`nginx/nginx.conf`、根目录 `docker-compose.yml`、`frontend/` 应被视为 **仓库根目录/host 侧资源**；
- 不应把它们当成“backend 容器内 pytest 一定可覆盖到的对象”；
- 这也说明“backend 容器 healthy / pytest 局部通过”与“根目录运维脚本/前端/部署文件已可正式使用”不是同一件事。

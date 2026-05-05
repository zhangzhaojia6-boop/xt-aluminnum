# CLI / Scripts / Rollout Lane Spec

> 日期：当前 main 基线
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
- live `/readyz`、`check_pilot_*`、`check_owner_account_bindings.py`、`dingtalk_cli.py` 之类命令可以实际跑通；
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

## 2. 当前证据快照

### 已验证本地证据
- `python -m pytest backend/tests -q --durations=10` → **652 passed，123 deselected，30 warnings**。
- `python -m pytest backend/tests -m frontend_contract -q` → **123 passed，652 deselected**。
- `python -m pytest backend/tests/test_wecom_group_bot.py -q` → **10 passed**，覆盖企业微信群机器人 publisher，同时确认企业微信用户消息路径已移除。
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q` → **76 passed**。
- `git diff --check` → 通过；仅有既有 LF/CRLF 提示。
- `python scripts/check_pilot_config.py --date <目标日期> --json` 是 Gate A 配置预检入口。
- `python scripts/check_owner_account_bindings.py --target-workshop-code <车间编码> --json` 是 owner / 机列账号绑定预检入口。
- `python scripts/dingtalk_cli.py status --json` 是钉钉配置状态预检入口。

### 当前放量判断
当前 main 已有 dev / trial / rollback 基础骨架，但本文件不再把旧日期的 live 阻断当成当前证据。正式放量前必须重新跑现场 `/readyz`、Gate A / B / C，并保存当次输出。

### 关键解释
`docker compose` 的容器健康检查探测的是 `/healthz`，不是 `/readyz`。因此：
- `backend=healthy` 只代表“服务活着”；
- **不代表** “已通过试点放量门槛”；
- 放量必须以 `/readyz` 和 Gate A / B / C 为准。

## 3. 命令 / 脚本分层

| 层级 | 命令/脚本 | 用途 | 当前标准 | 备注 |
|---|---|---|---|---|
| dev | `docker compose up -d --build` | 本地拉起整套栈 | local runnable | 需要现场按当前 `.env` 重跑 |
| dev | `docker compose ps` | 看服务状态 | local runnable | 只能证明进程/容器状态 |
| dev | `curl -k https://localhost/healthz` | 活性检查 | local runnable | 需在目标栈重跑 |
| dev | `python -m pytest backend/tests -q --durations=10` | 后端默认测试基线 | local runnable | 当前 652 passed，123 deselected，30 warnings |
| dev | `python -m pytest backend/tests -m frontend_contract -q` | 前端静态合同基线 | local runnable | 当前 123 passed，652 deselected |
| dev | `scripts/generate_env.py` | 生成根目录 `.env` 模板 | host-only local runnable | 是根目录脚本，不属于 backend 镜像内脚本 |
| dev | `cd frontend && npm run build` | 前端构建验证 | local runnable | 需在前端改动后重跑 |
| trial | `curl -k https://localhost/readyz` | 现场前 readiness 总闸门 | can trial | 正式放量前必须刷新证据 |
| trial | `python scripts/check_pilot_config.py --date <目标日期> --json` | Gate A 配置预检 | can trial | 使用目标业务日，不写死日期 |
| trial | `python scripts/check_pilot_metrics.py --date <目标日期> --json` | 每日试点复盘 | can trial | 依赖试点样本数据 |
| trial | `python scripts/check_pilot_anomalies.py --date <目标日期> --json` | 每日异常复盘 | can trial | 需结合填报样本判断 |
| trial | `python scripts/check_owner_account_bindings.py --target-workshop-code <车间编码> --json` | owner / 机列账号绑定预检 | can trial | 用于浏览器 / 钉钉试跑前核对 |
| trial | `python scripts/dingtalk_cli.py status --json` | 钉钉集成状态预检 | can trial | 不替代真实 H5 登录验收 |
| trial | `docs/pilot-readiness-checklist.md` 三个 Gate 命令 | 试点前预检留痕 | can trial → formal-use 入口 | 需要当次现场输出 |
| ops | `docker compose exec backend alembic upgrade head` | 正式环境 DB 迁移 | formal-use | 需备份后执行 |
| ops | `python scripts/init_master_data.py` | 初始化基础主数据 | formal-use | backend 容器启动命令已串联 |
| ops | `python scripts/init_real_master_data.py` | 初始化真实主数据 | formal-use | backend 容器启动命令已串联 |
| ops | `python scripts/create_admin.py` | 初始化/修复管理员账号 | formal-use | 会改库 |
| ops | `docker compose -f docker-compose.yml -f docker-compose.prod.yml config/up` | 生产覆盖验证/拉起 | formal-use | README 已列出；不属于日常试点排查 |
| rollback | `AUTO_PUBLISH_ENABLED=false` | 停自动发布 | formal-use rollback | 保留填报/校验/汇总 |
| rollback | `AUTO_PUSH_ENABLED=false` | 停消息推送 | formal-use rollback | 保留业务链路留痕 |
| rollback | `WORKFLOW_ENABLED=false` / `WECOM_BOT_ENABLED=false` | 停工作流触达 | formal-use rollback | `docs/workflow-rollout.md` 已定义 |
| rollback | `scripts/backup_db.sh` / `.ps1` | 回滚前备份 | formal-use rollback | 应先于迁移/正式放量 |
| rollback | `scripts/restore_db.sh` / `.ps1` | 数据库恢复 | formal-use rollback | 属于强回滚动作 |

## 4. 当前证据映射到三档标准

| 对象 | local runnable | can trial | formal-use | 结论 |
|---|---|---|---|---|
| `/healthz` | 是 | 否 | 否 | 只能证明服务活着 |
| `/readyz` | 是 | 是 | 待现场刷新 | 需要目标环境当次输出 |
| 后端默认 pytest | 是 | 是 | 否 | 覆盖代码基线，不替代 live gate |
| 前端静态合同 pytest | 是 | 是 | 否 | 覆盖合同漂移，不替代浏览器验收 |
| `check_pilot_config.py` | 是 | 是 | 待现场刷新 | 使用目标业务日 |
| `check_pilot_metrics.py` | 是 | 是 | 待现场刷新 | 依赖试点样本数据 |
| `check_pilot_anomalies.py` | 是 | 是 | 待现场刷新 | 需结合填报样本判断 |
| `check_owner_account_bindings.py` | 是 | 是 | 待现场刷新 | 需要目标车间编码与账号清单 |
| `dingtalk_cli.py status` | 是 | 是 | 待现场刷新 | 只证明配置状态，不证明 H5 端到端登录 |
| `scripts/generate_env.py` | 是（host） | 不直接作为 trial gate | 否 | 是 bootstrap 工具，不是放量证据 |
| backup / restore | 否（不建议日常试跑） | 否 | 是 | 属于正式运维/回滚命令 |

## 5. 当前结论

截至当前 main 基线：
- 该仓库的 CLI / scripts 体系已经具备 **dev + trial + rollback** 基础骨架；
- **formal-use 仍不能仅凭本地测试宣布满足**，必须刷新目标环境 `/readyz`、Gate A / B / C 和回滚留痕；
- 当前优先动作是按目标业务日和目标车间重跑：
  1. `python scripts/check_pilot_config.py --date <目标日期> --json`
  2. `python scripts/check_owner_account_bindings.py --target-workshop-code <车间编码> --json`
  3. `python scripts/dingtalk_cli.py status --json`
  4. live `/readyz`

只有这些现场证据同时成立后，才进入 formal-use 判断。

## 6. 一个需要特别注意的执行边界

`tests/test_generate_env_script.py`、`tests/test_nginx_https_config.py`、`tests/test_real_master_data.py`、`tests/test_rebranding.py` 都会读取仓库根目录文件；但 backend Docker 镜像的 build context 是 `./backend`，容器内只有 `/app` 内容，看不到这些根目录路径。因此：
- `scripts/generate_env.py`、`nginx/nginx.conf`、根目录 `docker-compose.yml`、`frontend/` 应被视为 **仓库根目录/host 侧资源**；
- 不应把它们当成“backend 容器内 pytest 一定可覆盖到的对象”；
- 这也说明“backend 容器 healthy / pytest 局部通过”与“根目录运维脚本/前端/部署文件已可正式使用”不是同一件事。

# 数据中枢当前部署状态

更新时间：2026-05-06 13:26:00 +08:00

## 1. 仓库状态

- 仓库：`https://github.com/zhangzhaojia6-boop/xt-aluminnum.git`
- 当前主线：`main`
- 当前记录基准：当前 `main` HEAD
- 本地与远端状态以 `git status --short --branch` 和 `git rev-parse --short origin/main` 为准
- PR 状态：`#1 fix: 收口管理占位路由与就绪配置阻断` 已合并并关闭
- 推荐服务器目录：`/srv/aluminum-bypass`
- 推荐部署命令：

```bash
cd /srv/aluminum-bypass
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

## 2. 当前产品口径

产品名称统一使用：`鑫泰铝业 数据中枢`。

用户入口：

- `/entry`：岗位填报端。
- `/entry/fill`：机台主操统一按卷填报。
- `/manage`：管理入口。
- `/manage/factory`：工厂驾驶舱。
- `/manage/admin/settings`：管理配置入口。

兼容入口：

- `/mobile` 会重定向到 `/entry`。
- `/review/*` 会重定向到 `/manage/*`。
- `/manage/admin`、`/admin`、`/admin/overview` 会重定向到 `/manage/admin/settings`。

已收口事项：

- 旧管理占位路由已移除。
- 主路径不再暴露“改造中”“待迁移”等占位文案。
- PR review 反馈的扫码取旧 MES 快照问题已修复：重复 QR 取最新快照，缺少 `mes_coil_snapshots` 表时仍可回退设备二维码。
- 管理端已上线卷级实时填报可见性：`pending + mobile_coil_agg` 作为 `卷级直录` 待确认流入展示，正式已确认日报口径不被普通 `pending` 数据污染。

## 3. 默认部署形态

默认使用 Docker Compose：

```text
nginx 容器: 80/443
backend 容器: 8000
db 容器: PostgreSQL 15
```

核心文件：

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `nginx/nginx.conf`
- `scripts/deploy_trial.sh`
- `scripts/check_trial_stack.sh`
- `scripts/go_live_gate.sh`
- `scripts/launch_cloud_trial.sh`
- `scripts/backup_db.sh`
- `scripts/restore_db.sh`

生产机必须自备：

- `.env`
- `ssl/cert.pem`
- `ssl/key.pem`

不要把 `.env`、证书、密钥、数据库备份提交到 Git。

当前 ECS 真实运行形态仍是历史 systemd 托管：

```text
公网 80/443
  -> 宿主机 nginx
  -> aluminum-bypass.service: 127.0.0.1:8000
  -> 宿主机 PostgreSQL
```

当前 ECS 已按 systemd 形态完成本轮更新；Docker Compose 仍是后续统一部署形态，但切换前不要直接抢占宿主机 80/443 端口。

## 4. 本地验证记录

在当前 `main` HEAD 上已完成代码与路由文档回归验证：

- `python -m pytest backend/tests -q --durations=10`：669 passed，124 deselected，30 warnings
- `python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q`：17 passed
- `python -m pytest backend/tests -m frontend_contract -q`：124 passed，669 deselected
- `npm --prefix frontend test`：114 passed
- `npm --prefix frontend run build`：通过
- `git diff --check`：通过

此前在 `main@b029db8` 上已完成部署闸门与容器可用性验证：

- `npm --prefix frontend run e2e -- e2e/admin-surface.spec.js --grep "admin surface is separate"`：1 passed
- `docker compose config --quiet`：通过
- `curl -k https://127.0.0.1/readyz`：HTTP 200
- `bash scripts/go_live_gate.sh https://example.invalid --dry-run --require-external`：正确显示 `GATE_EXTERNAL`
- `bash scripts/launch_cloud_trial.sh https://example.invalid --dry-run --require-external --pull`：正确透传 `--require-external`

`main@9130fb3` 之后，主线继续完成 workflow 状态措辞、中心页真实路由、未使用 mock、排班闸门时区、成本历史契约和 canonical 中心导航路径收口；当前文档以当前 `main` HEAD 为准。

本地 Docker 状态：

- `db`：healthy
- `backend`：healthy
- `nginx`：running

## 5. 当前 readyz 与配置闸门

本地 `/readyz` 已通过，返回的关键状态：

- `database=ok`
- `uploads=ok`
- `equipment_binding=ok`
- `schedule=ok`
- `pipeline=ok`
- `mes_sync=unconfigured`

`docker compose exec -T backend python scripts/check_statistics_module_ready.py --json` 仍然是预期 hard fail。原因不是数据库或代码阻断，而是正式外部联通尚未配置真实值：

- `MES_UNCONFIGURED`
- `WORKFLOW_DISABLED`
- `LLM_DISABLED`
- `DINGTALK_DISABLED`
- `APP_CONNECTION_DISABLED`

正式联通前可先生成不回显现有密钥的 `.env` 填写模板：

```bash
python scripts/check_statistics_module_ready.py --env-template
```

正式联通前必须在服务器 `.env` 写入真实值：

```dotenv
MES_ADAPTER=mvc
MES_MVC_BASE_URL=...
MES_MVC_USERNAME=...
MES_MVC_PASSWORD=...
WORKFLOW_ENABLED=true
DINGTALK_ENABLED=true
DINGTALK_CORP_ID=...
DINGTALK_APP_KEY=...
DINGTALK_APP_SECRET=...
DINGTALK_AGENT_ID=...
APP_CONNECTION_ENABLED=true
APP_CONNECTION_PUSH_MODE=enabled
APP_CONNECTION_API_BASE=...
APP_CONNECTION_API_KEY=...
```

如果现场使用 REST 形式的外部 MES，则改为：

```dotenv
MES_ADAPTER=rest_api
MES_API_BASE=...
MES_API_KEY=...
```

## 6. 远端与 Vercel 探测记录

最近一次 ECS 修复验证：2026-05-06 13:26 左右。

- SSH：`root@8.140.218.13` key 登录可用。
- 远端仓库：`/srv/aluminum-bypass` 已快进到当前 `main` HEAD，`HEAD` 与 `origin/main` 对齐，工作区干净。
- 远端运行形态：宿主机 nginx + `aluminum-bypass.service` + 宿主机 PostgreSQL；`docker compose ps` 当前无运行容器。
- 已用 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 完成 systemd 宿主机部署闭环。
- 本轮已部署 `main@54a09e0`：管理端实时态势第一屏新增“卷级直录分布”，线上 `LiveDashboard-CO0mybtJ.js` / `LiveDashboard-BHO0nfza.css` 已包含 `卷级直录分布`、`live-output-distribution` 和 `未绑定`。
- 本轮已部署 `main@1c00050`：管理端实时态势主聚合接入 `mobile_coil_agg` 卷级直录 fallback，线上 `LiveDashboard-CeSbJ94X.js` 已包含 `卷级直录` 和 `local_shift_data`。
- 本轮已部署 `main@7659225`：管理端实时态势页新增“外部联通闸门”卡，线上 `LiveDashboard-BXTGpXX4.js` / `dashboard-D6EhilfF.js` 已包含 `外部联通闸门`、`接口待返回`、`external-readiness` 和 `hard_issues`。
- 本轮已部署 `main@3e492f8`：管理端外部 MES 状态条显示运行配置缺口，线上 `LiveDashboard-BNcHeouG.js` 已包含 `required_env`、`缺少配置` 和 `MES_MVC_BASE_URL`。
- 本轮已部署 `main@38493da`：管理端车间机列页支持把未绑定 `mobile_coil_agg` 实时填报按车间/班次归入“未绑定机列”，线上 `MachineLineScreen-DL7qgGJc.js` / `MachineLineScreen-FDnJ2hSk.css` 已包含 `未绑定机列`、`machine_binding_status` 和 `fc-line__bar`。
- 本轮已部署 `main@8fc5ce0`：管理端用户管理页支持绑定机列，线上 `UserManagement-CvyvNRYK.js` 已包含 `绑定机列` 和 `bound_machine_id`。
- 上一轮已部署 `main@793918a`：管理端运维页新增外部 MES 状态条，线上 `LiveDashboard-CqFyBTcQ.js` / `LiveDashboard-WZX7jfx-.css` 已包含 `mes-connection-strip`、`外部 MES` 和 `MES_MVC_BASE_URL`。
- 更新前已创建数据库备份：`backups/systemd-predeploy-20260506-093253.dump`。
- 已执行后端依赖安装、Alembic 迁移、`init_master_data.py`、`init_real_master_data.py`、`create_admin.py`。
- `init_real_master_data.py` 同步默认试点排班后，目标日 `2026-05-06` readyz 统计 `schedule_row_count=195`。
- 已执行前端构建：`VITE_API_BASE_URL=/api/v1 npm run build`。
- 已修复 systemd backend `.env`：`APP_ENV=production`，`INIT_ADMIN_PASSWORD` 使用强密码；不输出真实密钥。
- 已执行 owner 账号绑定修复：`FACTORY-UM`、`FACTORY-IK`、`FACTORY-CT` 绑定到 `CPK`。
- 已验证虚拟角色二维码：`virtual_role_qr_active=96`，`virtual_role_qr_bound=96`。
- `http://8.140.218.13/readyz`：HTTP 200，返回后端 readyz JSON。
- `http://8.140.218.13/manage/admin/settings`：HTTP 200，返回前端 SPA。
- `http://8.140.218.13/manage/factory`：HTTP 200，返回前端 SPA。
- `http://8.140.218.13/manage/factory/machine-lines`：HTTP 200，返回前端 SPA。
- 生产前端资源 `FactoryDirector-CzchESVl.js` 已包含 `review-factory-live-chart`。
- 生产库 `2026-05-06` 卷级填报核对：`mobile_coil_entries=15`，`pending_mobile_coil_agg_rows=4`，`pending_mobile_coil_agg_output=120460.0`。
- 管理端上报状态服务已返回 `source_label=卷级直录`、`source_variant=coil`；工厂指挥服务 `factory_command_total_output_tons=120460.0`。
- 工厂指挥服务 `list_machine_lines()` 已返回 `LINES=4`，分别为 `workshop:3:shift:1:unbound=0.0`、`workshop:5:shift:1:unbound=9100.0`、`workshop:5:shift:3:unbound=74110.0`、`workshop:8:shift:3:unbound=37250.0`，全部 `machine_binding_status=unbound`、`freshness.source=local_shift_data`。
- 管理端实时态势 `/api/v1/aggregation/live?business_date=2026-05-06` 管理端探针返回 `data_source=local_shift_data`、`factory_output=120460.0`，未绑定临时机列为 `2050冷轧车间|未绑定机列 / 白班=9100.0`、`2050冷轧车间|未绑定机列 / 夜班=74110.0`、`精整车间|未绑定机列 / 夜班=37250.0`。
- ECS 到外部 MES 登录入口 `https://mes.xintaily.com/Login/Index` 网络可达：HTTP 200，`remote_ip=47.92.251.37`，`ssl_verify=0`，`time_total=0.767825s`；当前 MES 未联通不是服务器网络不可达。
- 线上部署代码的 `/api/v1/dashboard/external-readiness` 管理端探针返回 `status_code=200`、`hard_gate_passed=False`、`module_usable=False`、`external_connection_enabled=False`，`hard_issue_codes=MES_UNCONFIGURED,WORKFLOW_DISABLED,LLM_DISABLED,DINGTALK_DISABLED,APP_CONNECTION_DISABLED`。
- `/readyz` 关键状态：
  - `environment=production`
  - `database=ok`
  - `uploads=ok`
  - `equipment_binding=ok`
  - `schedule=ok`
  - `pipeline=ok`
  - `hard_gate_passed=true`
  - `mes_sync=unconfigured`
  - `required_env=MES_ADAPTER,MES_MVC_BASE_URL,MES_MVC_USERNAME,MES_MVC_PASSWORD`
  - `active_mobile_user_count=329`
  - `active_workshop_count=12`
  - `active_equipment_count=136`

域名链路诊断：

- `xtmijd.com` 当前只返回 SOA，无 A 记录，不能作为可访问域名使用。
- `www.xtmijd.com` 已解析到 `8.140.218.13`。
- 从服务器本机用 SNI 验证 `xtmijd.com:443 -> 127.0.0.1` 和 `xtmijd.com:443 -> 8.140.218.13`，`/readyz` 均为 HTTP 200，说明 nginx HTTPS server、证书文件和后端反代链路可用。
- 从本机公网访问 `http://www.xtmijd.com/readyz` 返回阿里云 `Server: Beaver` 的 `Non-compliance ICP Filing` 403 页面。
- 从本机公网访问 `https://www.xtmijd.com/readyz` 在 TLS 握手阶段 connection reset。

结论：HTTPS 域名链路当前阻塞在域名备案/接入合规层，不是应用 readyz、nginx upstream 或后端代码问题。本轮公网正向证据以 `http://8.140.218.13/readyz` 为准；正式对外域名需要完成 ICP 备案/接入或换用已备案域名。

外部正式联通闸门仍未通过，`python scripts/check_statistics_module_ready.py --json` 当前 hard fail 为：

- `MES_UNCONFIGURED`
- `WORKFLOW_DISABLED`
- `LLM_DISABLED`
- `DINGTALK_DISABLED`
- `APP_CONNECTION_DISABLED`

Vercel 主线探测：

- 最近一次可确认正向记录仍是 2026-05-05 12:47 左右：`/`、`/entry`、`/manage/admin` 返回前端挂载页，`/readyz` 返回前端 SPA shell 而不是后端 readyz JSON。
- 2026-05-06 08:07 左右从本机探测 `xt-aluminnum.vercel.app:443` TCP 不通，`curl -4 https://xt-aluminnum.vercel.app/` 连接超时；因此本轮不把 Vercel 作为当前可达证据。

结论：Vercel 当前只能作为前端静态部署证据，不能证明后端、数据库、外部 MES、钉钉或应用连接 API 已正式联通。ECS 当前后端、数据库、填报排班和 nginx 基础路由已恢复到 ready；正式完全体仍取决于域名备案/接入、外部 MES、Workflow、LLM、钉钉和应用连接 API 的真实配置与验收。

## 7. 一条命令更新上线

服务器 SSH 用户认证可用后执行：

```bash
cd /srv/aluminum-bypass
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

如果后续切回 Docker Compose 统一部署形态，并且 AI 已正式配置后希望一起检查：

```bash
./scripts/launch_cloud_trial.sh https://你的域名 --pull
```

如果 MES、钉钉和应用连接 API 已填入真实配置，正式上线时必须加外部联通闸门：

```bash
./scripts/deploy_systemd_host.sh --pull --require-external https://你的域名
```

上线后必须确认：

```bash
cd /srv/aluminum-bypass
systemctl is-active aluminum-bypass
systemctl is-active nginx
curl -fsS http://8.140.218.13/healthz
curl -fsS http://8.140.218.13/readyz
cd backend
.venv/bin/python scripts/check_statistics_module_ready.py --json
```

## 8. 生产环境变量底线

服务器 `.env` 至少确认：

- `APP_ENV=production`
- `POSTGRES_PASSWORD` 已替换强随机值
- `SECRET_KEY` 已替换 32 位以上强随机值
- `INIT_ADMIN_PASSWORD` 已替换 12 位以上强密码
- `CORS_ORIGINS=https://你的域名`
- `VITE_API_BASE_URL=/api/v1`

外部正式联通至少确认：

- MES adapter 已启用并能访问真实外部 MES。
- Workflow 已启用。
- 钉钉应用配置完整。
- 应用连接 API 已启用，且 push mode 为 `enabled`。

## 9. 回滚锚点

当前主线回滚锚点：

```bash
git rev-parse --short HEAD
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
./scripts/backup_db.sh
```

代码回滚：

```bash
git checkout <last-good-commit>
TRIAL_BASE_URL=https://你的域名 ./scripts/deploy_trial.sh
```

数据库回滚必须先做备份校验，不要直接覆盖生产库。

# 数据中枢当前部署状态

更新时间：2026-05-05 14:02:19 +08:00

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
./scripts/launch_cloud_trial.sh https://你的域名 --pull --skip-ai
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

## 4. 本地验证记录

在当前 `main` HEAD 上已完成代码与路由文档回归验证：

- `python -m pytest backend/tests -q`：676 passed，30 warnings
- `node --test tests/*.test.js`：82 passed
- `npm run build`：通过
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
- `DINGTALK_DISABLED`
- `APP_CONNECTION_DISABLED`

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

最近一次 ECS 只读探测：2026-05-05 12:20 左右。

- `8.140.218.13:22`：连接被远端关闭或超时，当前不能 SSH 登录。
- `8.140.218.13:443`：TCP 可达，但 SSH over 443 被远端关闭。
- `https://8.140.218.13/readyz`：HTTP 404。
- `http://8.140.218.13/readyz`：HTTP 503。

Vercel 主线探测：2026-05-05 12:47 左右。

- GitHub commit status：最近一次可确认记录为 `Vercel=success`，目标提交 `b029db8`；之后提交的 GitHub REST 查询曾被 rate limit 阻断，Vercel MCP 当前返回 403，本轮未把 Vercel 作为后端或外部联通证据。
- `https://xt-aluminnum.vercel.app/`：HTTP 200。
- `https://xt-aluminnum.vercel.app/entry`：HTTP 200，返回前端挂载页。
- `https://xt-aluminnum.vercel.app/manage/admin`：HTTP 200，返回前端挂载页。
- `https://xt-aluminnum.vercel.app/readyz`：HTTP 200，但返回的是前端 SPA shell，不是后端 readyz JSON。

结论：Vercel 当前只能作为前端静态部署证据，不能证明后端、数据库、MES、钉钉或应用连接 API 已正式联通。ECS 仍需恢复 SSH 或提供服务器执行结果后再验收。

## 7. 一条命令更新上线

服务器 SSH 恢复后执行：

```bash
cd /srv/aluminum-bypass
git fetch origin
git status --short --branch
git pull --ff-only origin main
./scripts/launch_cloud_trial.sh https://你的域名 --pull --skip-ai
```

如果 AI 已正式配置并希望一起检查：

```bash
./scripts/launch_cloud_trial.sh https://你的域名 --pull
```

如果 MES、钉钉和应用连接 API 已填入真实配置，正式上线时必须加外部联通闸门：

```bash
./scripts/launch_cloud_trial.sh https://你的域名 --pull --require-external
```

上线后必须确认：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
./scripts/check_trial_stack.sh https://你的域名
docker compose exec -T backend python scripts/check_statistics_module_ready.py
curl -kfsS https://你的域名/healthz
curl -kfsS https://你的域名/readyz
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

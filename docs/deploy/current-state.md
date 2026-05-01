# 数据中枢当前部署状态

更新时间：2026-05-01 16:40:04 +08:00

## 1. 仓库状态

- 仓库：`https://github.com/zhangzhaojia6-boop/xt-aluminnum.git`
- 分支：`main`
- 当前本地 HEAD：`3a3ebc6 feat: add ZXTF annealing workshop and per-machine energy reporting`
- 上一个已知云端 QA 提交：`6931c8d test: stabilize customer workflow e2e`
- 推荐服务器目录：`/srv/aluminum-bypass`
- 推荐部署命令：

```bash
cd /srv/aluminum-bypass
./scripts/launch_cloud_trial.sh https://your.domain.example --pull --skip-ai
```

## 2. 当前产品口径

产品名称统一使用：`鑫泰铝业 数据中枢`。

用户入口：

- `/entry`：岗位填报端。
- `/entry/fill`：机台主操统一按卷填报。
- `/manage`：管理与审阅入口。
- `/manage/factory`：工厂驾驶舱。
- `/manage/admin/templates`：主数据与模板中心。

兼容入口：

- `/mobile` 会重定向到 `/entry`。
- `/review/*` 会重定向到 `/manage/*`。

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

## 4. 环境变量状态

`.env` 不提交到 Git。服务器上建议通过以下命令生成：

```bash
python3 scripts/generate_env.py --app-env production --domain your.domain.example
```

上线前至少确认：

- `APP_ENV=production`
- `POSTGRES_PASSWORD` 已替换强随机值。
- `SECRET_KEY` 已替换 32 位以上强随机值。
- `INIT_ADMIN_PASSWORD` 已替换 12 位以上强密码。
- `CORS_ORIGINS=https://your.domain.example`
- `VITE_API_BASE_URL=/api/v1`

首轮浏览器试跑建议：

- `MES_ADAPTER=null`
- `WORKFLOW_ENABLED=false`
- `WECOM_APP_ENABLED=false`
- `WECOM_BOT_ENABLED=false`
- `LLM_ENABLED=false`
- `APP_CONNECTION_ENABLED=false`

## 5. 最近验证记录

在 `6931c8d` 前后完成过一次完整本地 QA：

- `npm run e2e`：48 passed
- `npm run build`：通过
- `python -m pytest`：514 passed, 28 warnings

当前 HEAD 已前进到 `3a3ebc6`，正式部署前仍应在本地或服务器重新跑：

```bash
cd frontend
npm run build
npm run e2e

cd ../backend
python -m pytest
```

如果服务器资源有限，至少执行：

```bash
./scripts/launch_cloud_trial.sh https://your.domain.example --pull --skip-ai
```

并确认 `go_live_gate` 通过。

## 6. 已知本地工作树注意事项

当前本地工作树存在未跟踪草稿文件，部署文档提交时不要误带：

- `backend/scripts/deploy_zxtf_update.py`
- `docs/superpowers/plans/2026-05-01-backend-service-split.md`
- `docs/superpowers/plans/2026-05-01-frontend-large-file-treatment.md`

这些文件是否保留、提交或删除，需要另行确认。

## 7. 首次上云待办

1. 阿里云安全组开放 TCP `80`、`443`，TCP `22` 仅允许管理 IP。
2. 服务器安装 `git`、`curl`、`docker`、`docker compose plugin`、`python3`。
3. 在 `/srv/aluminum-bypass` clone 当前仓库。
4. 生成并检查 `.env`。
5. 放入正式 HTTPS 证书。
6. 执行：

```bash
TRIAL_BASE_URL=https://your.domain.example ./scripts/deploy_trial.sh
```

7. 浏览器验证 `/`、`/entry`、`/manage/factory`。
8. 使用管理员和一个机台/主操账号做真实登录和测试填报。

## 8. 日常发布流程

本地：

```bash
git status --short
# 修改代码
# 跑相关测试
git add <verified files>
git commit -m "type: message"
git push origin main
```

服务器：

```bash
cd /srv/aluminum-bypass
./scripts/launch_cloud_trial.sh https://your.domain.example --pull --skip-ai
```

上线后：

```bash
./scripts/check_trial_stack.sh https://your.domain.example
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## 9. 回滚锚点

部署前记录：

```bash
git rev-parse --short HEAD
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
./scripts/backup_db.sh
```

代码回滚：

```bash
git checkout <last-good-commit>
TRIAL_BASE_URL=https://your.domain.example ./scripts/deploy_trial.sh
```

数据库回滚必须先做备份校验，不要直接覆盖生产库。

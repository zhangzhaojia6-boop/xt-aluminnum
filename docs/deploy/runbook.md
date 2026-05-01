# 数据中枢云服务器部署 Runbook

本文档用于把 `鑫泰铝业 数据中枢` 放到一台 Linux 云服务器上，并让后续更新固定为：

```text
本地开发 -> 测试 -> git push -> 服务器 git pull -> 一条部署命令上线
```

## 1. 推荐拓扑

默认使用仓库内置 Docker Compose：

```text
公网 80/443
  -> nginx 容器
  -> backend 容器:8000
  -> PostgreSQL 容器:5432
```

默认文件：

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `nginx/nginx.conf`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `.env`
- `ssl/cert.pem`
- `ssl/key.pem`

不提交到 Git 的文件：

- `.env`
- `ssl/`
- `backups/`
- `frontend/dist/`
- 任何真实密钥、证书、数据库备份

## 2. 服务器首次准备

以 Ubuntu 22.04/24.04 为例：

```bash
sudo apt update
sudo apt install -y git curl ca-certificates docker.io docker-compose-plugin python3
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

重新登录一次 SSH 后检查：

```bash
docker --version
docker compose version
docker info >/dev/null
```

安全组建议：

- 入方向 TCP `22` 只放行管理人员固定公网 IP。
- 入方向 TCP `80`、`443` 放行公网访问。
- 不开放数据库端口 `5432` 到公网。

## 3. 拉取仓库

首次部署：

```bash
sudo mkdir -p /srv/aluminum-bypass
sudo chown -R "$USER":"$USER" /srv/aluminum-bypass
cd /srv/aluminum-bypass
git clone https://github.com/zhangzhaojia6-boop/xt-aluminnum.git .
git checkout main
```

已有目录时更新：

```bash
cd /srv/aluminum-bypass
git fetch origin
git status --short --branch
git pull --ff-only origin main
```

如果服务器上出现未提交改动，先停下来确认，避免把生产配置或现场数据误覆盖。

## 4. 配置生产环境变量

推荐用脚本生成安全 `.env`：

```bash
cd /srv/aluminum-bypass
python3 scripts/generate_env.py --app-env production --domain your.domain.example
```

然后编辑 `.env`：

```bash
nano .env
```

上线前至少确认：

```env
APP_ENV=production
POSTGRES_USER=bypass_user
POSTGRES_PASSWORD=请使用强随机值
POSTGRES_DB=aluminum_bypass
SECRET_KEY=至少32位强随机值
CORS_ORIGINS=https://your.domain.example
INIT_ADMIN_USERNAME=admin
INIT_ADMIN_PASSWORD=至少12位强密码
INIT_ADMIN_NAME=系统管理员
DEFAULT_TIMEZONE=Asia/Shanghai
VITE_API_BASE_URL=/api/v1
```

首轮浏览器试跑推荐保持：

```env
MES_ADAPTER=null
WORKFLOW_ENABLED=false
WECOM_APP_ENABLED=false
WECOM_BOT_ENABLED=false
LLM_ENABLED=false
APP_CONNECTION_ENABLED=false
```

如需 AI 助手，再单独启用 `LLM_ENABLED=true` 并配置服务商 API Key。

## 5. 配置 HTTPS 证书

默认 nginx 容器读取：

```text
ssl/cert.pem
ssl/key.pem
```

准备目录：

```bash
cd /srv/aluminum-bypass
mkdir -p ssl
chmod 700 ssl
```

把证书和私钥放入：

```bash
ls -l ssl/cert.pem ssl/key.pem
grep -q "BEGIN CERTIFICATE" ssl/cert.pem
grep -q "PRIVATE KEY" ssl/key.pem
```

没有正式证书时可以先用临时自签证书做内测，但正式现场必须换成域名证书。

## 6. 首次启动

先看 compose 渲染结果：

```bash
cd /srv/aluminum-bypass
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

部署：

```bash
TRIAL_BASE_URL=https://your.domain.example ./scripts/deploy_trial.sh
```

这个脚本会检查 `.env`、证书、Docker 环境，然后执行：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
./scripts/check_trial_stack.sh "$TRIAL_BASE_URL"
```

## 7. 一条命令更新上线

以后本地完成代码、测试、commit、push 后，服务器执行：

```bash
cd /srv/aluminum-bypass
./scripts/launch_cloud_trial.sh https://your.domain.example --pull --skip-ai
```

含义：

- `--pull`：先 `git pull` 拉取 GitHub 最新 `main`。
- `deploy_trial.sh`：重建并启动 Docker Compose。
- `go_live_gate.sh`：跑上线闸门。
- `--skip-ai`：AI 服务未正式配置前跳过 AI live 探针。

如果 AI 已配置并希望一起检查：

```bash
./scripts/launch_cloud_trial.sh https://your.domain.example --pull
```

演练模式：

```bash
./scripts/launch_cloud_trial.sh https://your.domain.example --pull --dry-run
```

## 8. 部署后验收

服务器上检查：

```bash
cd /srv/aluminum-bypass
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
./scripts/check_trial_stack.sh https://your.domain.example
curl -kfsS https://your.domain.example/healthz
curl -kfsS https://your.domain.example/readyz
```

浏览器检查：

- `https://your.domain.example/`
- `https://your.domain.example/entry`
- `https://your.domain.example/manage/factory`
- 管理员登录
- 机台或主操账号登录
- 提交一条测试填报
- 管理端确认数据可见

## 9. 日常运维命令

查看状态：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

查看日志：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail 200
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx --tail 200
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs db --tail 100
```

重启后端：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```

停机：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

不要随意加 `-v`，否则会删除数据库卷。

## 10. 备份和恢复

备份：

```bash
cd /srv/aluminum-bypass
./scripts/backup_db.sh
```

恢复前校验：

```bash
./scripts/restore_db.sh --dry-run backups/your-backup.dump
```

真实恢复前先确认：

- 当前版本 commit。
- 备份文件日期。
- 是否需要停业务窗口。
- 是否涉及 Alembic 迁移回退。

## 11. 回滚

只回滚代码：

```bash
cd /srv/aluminum-bypass
git log --oneline -5
git checkout <上一个稳定commit>
TRIAL_BASE_URL=https://your.domain.example ./scripts/deploy_trial.sh
```

确认恢复后再决定是否把 `main` 回退或追加一个修复 commit。不要直接重写远端历史。

如果怀疑数据库数据问题，先备份当前库，再做恢复演练，不要直接覆盖生产库。

## 12. systemd 可选托管

默认直接用 Docker Compose 即可。若希望开机自动拉起，可创建：

```bash
sudo nano /etc/systemd/system/aluminum-bypass.service
```

内容：

```ini
[Unit]
Description=Aluminum Bypass Docker Compose stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
WorkingDirectory=/srv/aluminum-bypass
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml down
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable aluminum-bypass
sudo systemctl start aluminum-bypass
sudo systemctl status aluminum-bypass --no-pager
```

更新发布仍建议用：

```bash
cd /srv/aluminum-bypass
./scripts/launch_cloud_trial.sh https://your.domain.example --pull --skip-ai
```

## 13. 故障定位顺序

1. `git status --short --branch`
2. `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps`
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail 200`
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx --tail 200`
5. `curl -k https://your.domain.example/healthz`
6. `curl -k https://your.domain.example/readyz`
7. 检查 `.env`、证书、安全组、域名解析。

常见问题：

- SSH 不通：先看安全组、fail2ban、`/etc/hosts.deny`。
- 80 通 443 不通：检查证书文件、nginx 日志、安全组 443。
- `/readyz` 不通过：先看后端日志和数据库连接。
- 前端能打开但 API 失败：检查 `/api/` 反代、`VITE_API_BASE_URL=/api/v1`、`CORS_ORIGINS`。
- 登录失败：检查 `INIT_ADMIN_PASSWORD` 是否是初始化时的密码；已有数据库不会因为改 `.env` 自动改老账号密码。

## 14. 发布纪律

- 本地先跑相关测试，再 commit 和 push。
- 服务器只从 `origin/main` 拉代码。
- 生产 `.env` 和证书只留在服务器。
- 每次上线前确认当前 commit。
- 每次上线后跑健康检查和浏览器主路径验收。

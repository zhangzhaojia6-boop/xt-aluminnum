# 部署说明

## 当前生产部署方式

**生产环境使用 systemd + nginx 部署，不是 Docker Compose。**

### 生产部署流程

```bash
# 1. 使用 SSH key 登录云端
ssh root@8.140.218.13

# 2. 进入仓库
cd /srv/aluminum-bypass

# 3. 执行宿主机 systemd 部署脚本
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13

# 4. 验证服务
curl http://localhost/readyz
curl http://localhost/api/v1/healthz
```

### 部署脚本

首选脚本：

```bash
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

这个脚本必须在云端 `/srv/aluminum-bypass` 内执行，会自动拉取代码、备份、迁移、重启服务、构建前端并验证 `/readyz`。

备用脚本 `scripts/deploy_remote.sh` 也是云端脚本，不是本地远程登录脚本。

仓库不再保留含明文密码的部署脚本；远程登录统一使用 SSH key 或云厂商密钥管理。

## 本地开发

本地开发使用 SQLite 数据库，不连接生产环境。

```bash
# 1. 配置本地环境
cp backend/.env.example backend/.env

# 2. 启动后端（开发模式）
cd backend
uvicorn app.main:app --reload

# 3. 启动前端（开发模式）
cd frontend
npm run dev
```

## Docker Compose（未来计划）

Docker Compose 配置已准备，但当前生产环境未使用。

```bash
# 开发环境
docker compose up -d

# 生产环境（未来）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 安全注意事项

1. **本地 `.env` 使用 SQLite**，不连接生产数据库
2. **生产 PostgreSQL 只监听 localhost**，外网无法访问
3. **不要提交 `.env` 文件到 Git**
4. **生产凭据保存在云端 `/srv/aluminum-bypass/backend/.env`**
5. **运维脚本需要密码时从环境变量读取**，例如 `PROD_DB_PASSWORD` 或 `ADMIN_NEW_PASSWORD`

## 清理临时文件

```bash
make clean          # 清理所有临时文件
make clean-pyc      # 只清理 Python 缓存
make clean-test     # 只清理测试文件
make clean-build    # 只清理构建产物
```

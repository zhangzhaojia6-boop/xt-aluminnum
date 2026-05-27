# 部署说明

## 当前生产部署方式

**生产环境使用 systemd + nginx 部署，不是 Docker Compose。**

### 生产部署流程

```bash
# 1. SSH 到云端
ssh root@8.140.218.13

# 2. 拉取最新代码
cd /srv/aluminum-bypass
git pull

# 3. 重启后端服务
systemctl restart aluminum-bypass

# 4. 重新构建前端（如有前端改动）
cd frontend
npm run build
nginx -s reload

# 5. 验证服务
curl http://localhost/readyz
```

### 自动化部署脚本

使用 `scripts/deploy_remote.sh`：

```bash
./scripts/deploy_remote.sh
```

该脚本会自动：
1. SSH 到云端
2. 拉取代码
3. 重启后端
4. 重建前端
5. 验证服务状态

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

## 清理临时文件

```bash
make clean          # 清理所有临时文件
make clean-pyc      # 只清理 Python 缓存
make clean-test     # 只清理测试文件
make clean-build    # 只清理构建产物
```

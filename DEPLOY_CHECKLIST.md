# 部署检查清单

每次同步代码到云端后，必须按顺序执行：

## 1. 同步代码
```bash
cd /srv/aluminum-bypass
git pull origin main
```

## 2. 后端依赖（如有新增）
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 3. 数据库迁移（如有新增）
```bash
alembic upgrade head
```

## 4. **重建前端（必须）**
```bash
cd frontend
npm run build
```

## 5. 重启后端服务
```bash
sudo systemctl restart aluminum-bypass
```

## 6. 重载 Nginx（如有前端变更）
```bash
sudo nginx -s reload
```

## 常见问题

### 前端改动不生效
- **症状**：代码已 push，git pull 成功，但页面行为没变
- **原因**：忘记 `npm run build`
- **解决**：执行步骤 4

### 后端改动不生效
- **症状**：API 行为没变
- **原因**：忘记重启服务
- **解决**：执行步骤 5

### 数据库字段缺失
- **症状**：500 错误，日志显示字段不存在
- **原因**：忘记 `alembic upgrade`
- **解决**：执行步骤 3

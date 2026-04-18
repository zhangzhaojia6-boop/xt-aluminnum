# 试点上线部署方案

> **目标：** 以最小改动让系统从开发机上线，20 名车间员工可通过手机（4G/任意网络）访问填报。
>
> **约束：** 部署在当前 Windows 11 开发机，车间网络无法直连开发机，需内网穿透。

---

## 架构总览

```
员工手机 (4G / Wi-Fi)
        │
        ▼
  Cloudflare Edge (免费, 自动 SSL)
   └── https://mes.xt-alu.com
        │ (加密隧道)
        ▼
  cloudflared (开发机上运行)
        │
        ▼
  Docker Compose (开发机)
   ├── nginx (:443) ← Cloudflare 终止外层 SSL，内层走 HTTP 即可
   ├── backend (:8000) ← FastAPI + 4 workers
   ├── db (:5432) ← PostgreSQL 15, pgdata 卷
   └── [不改动] 现有所有业务逻辑
```

---

## 上线前必做清单（共 6 步）

### 步骤 1：生成生产级凭证

当前 `.env` 使用弱密码（`bypass_pass_2024`、`Admin@123456`）。

**执行：**
```bash
python scripts/generate_env.py
```

该脚本自动生成：
- `POSTGRES_PASSWORD`：32 位随机 hex
- `SECRET_KEY`：64 位随机 hex
- `INIT_ADMIN_PASSWORD`：24 位 URL-safe 随机串

**注意：** 生成后需要重建数据库（或 `ALTER USER` 改密码），因为 PostgreSQL 密码在首次 `initdb` 时写入。如果要保留现有数据，用以下方式改密码而非重建：

```sql
ALTER USER bypass_user WITH PASSWORD 'NEW_PASSWORD_HERE';
```

### 步骤 2：注册域名 + 配置 Cloudflare

1. 在任意注册商（阿里云万网、Namesilo 等）注册域名，建议简短如 `xt-alu.com`
2. 登录 Cloudflare 控制台 → Add Site → 输入域名 → 选 Free Plan
3. 按提示将域名 NS 记录改为 Cloudflare 提供的 nameserver
4. 等 DNS 生效（通常 5-30 分钟）

### 步骤 3：安装 cloudflared 并创建隧道

```powershell
# Windows 上安装 cloudflared
winget install Cloudflare.cloudflared

# 登录 Cloudflare 账户
cloudflared tunnel login

# 创建隧道
cloudflared tunnel create xt-aluminum

# 配置路由：将域名指向隧道
cloudflared tunnel route dns xt-aluminum mes.xt-alu.com
```

创建配置文件 `C:\Users\xt\.cloudflared\config.yml`：

```yaml
tunnel: <tunnel-id>  # 创建隧道后显示的 UUID
credentials-file: C:\Users\xt\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: mes.xt-alu.com
    service: https://localhost:443
    originRequest:
      noTLSVerify: true  # 因为内部 nginx 用自签名证书
  - service: http_status:404
```

```powershell
# 作为 Windows 服务安装（开机自启）
cloudflared service install

# 或前台运行测试
cloudflared tunnel run xt-aluminum
```

### 步骤 4：更新 CORS 和安全配置

修改 `.env` 添加新域名到 CORS 允许列表：

```env
CORS_ORIGINS=http://localhost:8080,http://localhost:3000,http://localhost:5173,https://mes.xt-alu.com
```

修改 `backend/app/config.py` 中的生产环境检测，确保 `APP_ENV=production` 时不会因为弱密码阻止启动（因为步骤 1 已更换）。

### 步骤 5：用生产配置启动服务

```bash
# 停掉开发环境
docker compose down

# 用生产配置启动（4 workers, 资源限制, restart policy）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

验证：
```bash
# 检查服务状态
docker compose ps

# 检查后端日志
docker compose logs backend --tail=50

# 从外网访问测试
curl -I https://mes.xt-alu.com/healthz
```

### 步骤 6：配置自动备份

创建 Windows 计划任务，每天凌晨 2 点自动备份：

```powershell
# 创建备份目录
mkdir D:\zzj-backups

# 测试备份脚本
bash scripts/backup_db.sh D:\zzj-backups\test.dump
```

用 Windows 任务计划程序创建定时任务：
- 触发器：每天 02:00
- 操作：`bash scripts/backup_db.sh D:\zzj-backups\postgres-%date:~0,4%%date:~5,2%%date:~8,2%.dump`

---

## 上线后立即可用的功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 管理员后台 | ✅ 可用 | 车间/班组/人员/模板管理 |
| 手机填报 | ✅ 可用 | 管理员+班长角色均可填写 |
| 生产驾驶舱 | ✅ 可用 | 厂长看板 + 车间主任看板 |
| 审核流程 | ✅ 可用 | 班次审核/退回 |
| Excel 导入 | ✅ 可用 | 考勤/产量/能耗批量导入 |
| OCR 拍照识别 | ✅ 可用 | Tesseract 本地识别 |
| 钉钉接入 | ⏳ 二期 | 框架已就绪，需配置凭证 |
| AI 助手 | ⏳ 三期 | 待设计 |
| MES 对接 | ⏳ 后续 | 适配器已预留 |

---

## 试点范围建议

基于系统现有数据，**铸锭车间（ZD）** 最适合首批试点：
- 已有完整的产量数据（1175 吨/天）
- 模板字段最成熟（6 个核心字段已验证）
- 有机台账号 ZD-1 且 Playwright 测试全部通过
- 慢工序，填报节奏从容，适合用户适应期

**建议试点节奏：**
1. **第 1 周：** 仅管理员 + 铸锭车间班长（3-5 人）试用
2. **第 2 周：** 扩展到铸锭全车间（含机台操作员）
3. **第 3 周起：** 视反馈扩展到热轧、冷轧车间

---

## 后续迭代路线图（上线后按优先级推进）

| 优先级 | 功能 | 依赖 |
|--------|------|------|
| P0 | 钉钉 H5 免登 + 消息推送 | 域名上线后配置凭证即可 |
| P1 | AI 问答助手（生产数据查询） | Anthropic API Key |
| P1 | 数据库维护工具（清理/归档） | 上线运行后根据数据量决定 |
| P2 | AI 分析助手（趋势/异常分析） | 依赖 P1 的 AI 网关 |
| P2 | MES 系统对接 | 需 MES 方提供 API 文档 |
| P3 | 多智能体模式 | 依赖 P1/P2 AI 基础设施 |

---

## 风险与兜底

| 风险 | 应对 |
|------|------|
| 开发机断电/重启 | Docker `restart: unless-stopped` + cloudflared 服务自启 |
| 数据丢失 | 每日自动备份 + 手动备份脚本 |
| 隧道不稳定 | cloudflared 自动重连；Cloudflare 免费套餐 SLA 99.9% |
| 员工不会用 | 第 1 周仅 3-5 人，面对面培训 |
| 需要回滚 | `restore_db.sh` 可恢复任意备份点 |

---

## 交给 Codex 的执行任务

以上步骤 1-6 中，**步骤 1（生成凭证）和步骤 4（CORS 配置）** 可以直接交给 Codex 自动执行。其余步骤涉及外部操作（域名注册、Cloudflare 控制台、Windows 任务计划），需要你手动完成。

Codex 可执行任务：
1. 更新 `.env` 中的 CORS_ORIGINS 加入新域名
2. 创建 `cloudflared` 配置文件模板
3. 创建 PowerShell 自动备份脚本
4. 添加 `docker-compose.prod.yml` 中缺少的 cloudflared 服务（可选）
5. 更新 nginx.conf 优化生产配置（如果需要）

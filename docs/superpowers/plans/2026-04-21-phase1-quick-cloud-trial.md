# Phase 1 Quick Cloud Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前系统收口成一个可在单机 Linux 云主机上进行一个车间浏览器快速试跑的版本，并补齐 GitHub、生产 `.env`、部署、备份、回滚和验收路径。

**Architecture:** 继续复用现有 `docker-compose.yml + docker-compose.prod.yml` 的单机栈，不引入新基础设施。实现重点放在“发布基线清理、文档和脚本收口、环境变量生成、云上部署命令、备份恢复、最小试跑验收”六条线上，让首次上云尽量低门槛，同时为后续通过 GitHub `git pull` 快速迭代铺路。

**Tech Stack:** Git/GitHub、Docker Compose、Nginx、FastAPI、PostgreSQL 15、Python 3.11、POSIX shell、pytest

---

## File Structure

- Modify: `.gitignore`
  - 收口快速试跑阶段的临时目录、截图、pytest 残留和错误生成目录，帮助形成发布候选工作区
- Modify: `README.md`
  - 把 GitHub 先接入、快速试跑定位和最小部署路径写清楚
- Modify: `docs/部署文档.md`
  - 收成“快速试跑优先”的操作文档，明确 GitHub 拉取、单机部署、验收和回滚
- Modify: `docs/发布冻结基线清单.md`
  - 增加“工作区清洁、GitHub 已接入、快速试跑范围”冻结条件
- Modify: `docs/现场UAT清单.md`
  - 对齐一个车间快速试跑的管理员/主操/专项 owner 验收路径
- Create: `docs/快速试跑运维手册.md`
  - 给代码小白使用的一页式部署、更新、日志、备份、恢复手册
- Modify: `.env.example`
  - 补充快速试跑推荐值和浏览器试跑边界说明
- Modify: `scripts/generate_env.py`
  - 支持生成更贴合快速试跑的生产 `.env`，减少手填风险
- Create: `scripts/deploy_trial.sh`
  - 一键执行生产 compose 配置检查和启动
- Create: `scripts/check_trial_stack.sh`
  - 一键验证 `healthz / readyz / compose ps`
- Modify: `scripts/backup_db.sh`
  - 默认适配 `docker-compose.yml + docker-compose.prod.yml` 的快速试跑备份路径
- Modify: `scripts/restore_db.sh`
  - 默认适配 `docker-compose.yml + docker-compose.prod.yml` 的快速试跑恢复校验路径
- Create: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
  - 锁定文档、忽略规则和运维脚本 contract，防止后续回退
- Create: `backend/tests/test_generate_env_script.py`
  - 锁定 `.env` 生成脚本的快速试跑输出 contract

## External Inputs Required During Execution

- 用户提供的 GitHub 仓库 URL
- 用户提供的 Linux 云主机 SSH 登录方式
- 已解析到云主机的域名
- 正式 HTTPS 证书文件或证书申请方式

### Task 1: 冻结发布候选工作区

**Files:**
- Modify: `.gitignore`
- Modify: `docs/发布冻结基线清单.md`
- Create: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [ ] **Step 1: 写一个失败的静态测试，锁定快速试跑的工作区清洁规则**

```python
from pathlib import Path


def test_gitignore_covers_quick_trial_artifacts() -> None:
    source = Path(".gitignore").read_text(encoding="utf-8")
    assert ".tmp-pytest/" in source
    assert "backend/.pytest-cache/" in source
    assert "backend/.pytest-cache-2/" in source
    assert "backend/pytest-cache-files-*/" in source
    assert "frontend/tmp-review-home.png" in source
    assert "frontend/frontend/" in source
```

- [ ] **Step 2: 运行测试确认当前规则还不完整**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_gitignore_covers_quick_trial_artifacts -q`

Expected: FAIL，提示缺少一个或多个快速试跑临时产物忽略规则。

- [ ] **Step 3: 最小修改 `.gitignore` 和冻结清单**

```gitignore
.tmp-pytest/
backend/.pytest-cache/
backend/.pytest-cache-2/
backend/pytest-cache-files-*/
frontend/tmp-review-home.png
frontend/frontend/
```

```md
## 冻结前最后确认

5. `git status --short` 不再包含测试缓存、临时截图和误生成目录
6. GitHub 远端已接入，云主机可直接拉代码
```

- [ ] **Step 4: 重跑静态测试确认通过**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_gitignore_covers_quick_trial_artifacts -q`

Expected: PASS

- [ ] **Step 5: 提交这一小步**

```bash
git add .gitignore docs/发布冻结基线清单.md backend/tests/test_quick_cloud_trial_docs_and_ops.py
git commit -m "chore: 收口快速试跑发布候选工作区规则"
```

### Task 2: 收口 GitHub + 快速试跑发布文档

**Files:**
- Modify: `README.md`
- Modify: `docs/部署文档.md`
- Modify: `docs/现场UAT清单.md`
- Create: `docs/快速试跑运维手册.md`
- Test: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [ ] **Step 1: 写失败测试，锁定 GitHub 优先和一个车间试跑文档口径**

```python
def test_quick_trial_docs_require_github_and_single_workshop_rollout() -> None:
    deployment = Path("docs/部署文档.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    uat = Path("docs/现场UAT清单.md").read_text(encoding="utf-8")

    assert "GitHub" in deployment
    assert "git pull" in deployment
    assert "一个车间" in deployment
    assert "企业微信正式入口先不接" in deployment
    assert "1 个管理员" in uat
    assert "1 个车间的主操/机台账号" in uat
    assert "专项 owner" in uat
    assert "GitHub / 上云前封装准备" in readme
```

- [ ] **Step 2: 运行测试确认现有文档还没完全对齐**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_quick_trial_docs_require_github_and_single_workshop_rollout -q`

Expected: FAIL，提示文档缺少 `git pull`、一个车间试跑或浏览器快速试跑边界。

- [ ] **Step 3: 最小修改文档，不扩新范围**

```md
## GitHub 与发布方式

1. 上云前先接 GitHub 远端
2. 云主机通过 `git clone` / `git pull` 更新代码
3. 生产 `.env`、证书和密钥不进仓库
```

```md
## Day 1 快速试跑验收对象

1. 1 个管理员
2. 1 个车间主操/机台账号
3. 1-2 个专项 owner
```

- [ ] **Step 4: 新建一页式运维手册**

```md
# 快速试跑运维手册

1. 部署：`./scripts/deploy_trial.sh`
2. 健康检查：`./scripts/check_trial_stack.sh`
3. 备份：`./scripts/backup_db.sh`
4. 恢复：`./scripts/restore_db.sh backups/<file>`
5. 日志：`docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail 200`
```

- [ ] **Step 5: 重跑文档静态测试**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_quick_trial_docs_require_github_and_single_workshop_rollout -q`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add README.md docs/部署文档.md docs/现场UAT清单.md docs/快速试跑运维手册.md backend/tests/test_quick_cloud_trial_docs_and_ops.py
git commit -m "docs: 收口快速试跑上云与验收文档"
```

### Task 3: 让 `.env` 生成脚本适配快速试跑

**Files:**
- Modify: `.env.example`
- Modify: `scripts/generate_env.py`
- Create: `backend/tests/test_generate_env_script.py`

- [ ] **Step 1: 写失败测试，锁定快速试跑 `.env` contract**

```python
from scripts.generate_env import build_env_content


def test_build_env_content_for_quick_trial_production() -> None:
    content = build_env_content(
        postgres_password="pw",
        secret_key="secret",
        admin_password="adminpw",
        dingtalk_corp_id="",
        dingtalk_app_key="",
        dingtalk_app_secret="",
        dingtalk_agent_id="",
        app_env="production",
        cors_origins="https://trial.example.com",
    )

    assert "APP_ENV=production" in content
    assert "CORS_ORIGINS=https://trial.example.com" in content
    assert "WECOM_APP_ENABLED=false" in content
    assert "AUTO_PUBLISH_ENABLED=true" in content
```

- [ ] **Step 2: 运行测试确认当前函数签名和输出不满足要求**

Run: `python -m pytest backend/tests/test_generate_env_script.py::test_build_env_content_for_quick_trial_production -q`

Expected: FAIL，原因类似参数不存在或输出还是 `APP_ENV=development`。

- [ ] **Step 3: 最小修改脚本，支持快速试跑生产输出**

```python
def build_env_content(..., app_env: str, cors_origins: str) -> str:
    lines = [
        f"APP_ENV={app_env}",
        f"CORS_ORIGINS={cors_origins}",
        "WECOM_APP_ENABLED=false",
    ]
```

```python
parser.add_argument("--app-env", default="production")
parser.add_argument("--domain", required=True)
parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
```

- [ ] **Step 4: 同步 `.env.example` 注释，明确快速试跑推荐值**

```env
# Quick cloud trial recommended values
APP_ENV=production
WECOM_APP_ENABLED=false
MES_ADAPTER=null
```

- [ ] **Step 5: 重跑脚本测试**

Run: `python -m pytest backend/tests/test_generate_env_script.py -q`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add .env.example scripts/generate_env.py backend/tests/test_generate_env_script.py
git commit -m "feat: 支持快速试跑生产环境变量生成"
```

### Task 4: 补齐一键部署和健康检查脚本

**Files:**
- Create: `scripts/deploy_trial.sh`
- Create: `scripts/check_trial_stack.sh`
- Test: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [ ] **Step 1: 写失败测试，锁定部署脚本 contract**

```python
def test_quick_trial_ops_scripts_exist_with_expected_commands() -> None:
    deploy = Path("scripts/deploy_trial.sh").read_text(encoding="utf-8")
    check = Path("scripts/check_trial_stack.sh").read_text(encoding="utf-8")

    assert "docker compose -f docker-compose.yml -f docker-compose.prod.yml config" in deploy
    assert "docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build" in deploy
    assert "curl -fsS https://" in check or "curl -k https://" in check
    assert "/readyz" in check
```

- [ ] **Step 2: 运行测试确认脚本尚不存在**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_quick_trial_ops_scripts_exist_with_expected_commands -q`

Expected: FAIL，提示脚本文件不存在。

- [ ] **Step 3: 新建最小部署脚本**

```sh
#!/usr/bin/env sh
set -eu

docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

- [ ] **Step 4: 新建最小健康检查脚本**

```sh
#!/usr/bin/env sh
set -eu

BASE_URL="${1:?Usage: scripts/check_trial_stack.sh https://trial.example.com}"
curl -fsS "$BASE_URL/healthz"
curl -fsS "$BASE_URL/readyz"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

- [ ] **Step 5: 重跑脚本 contract 测试**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_quick_trial_ops_scripts_exist_with_expected_commands -q`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add scripts/deploy_trial.sh scripts/check_trial_stack.sh backend/tests/test_quick_cloud_trial_docs_and_ops.py
git commit -m "feat: 添加快速试跑部署与健康检查脚本"
```

### Task 5: 收口备份与恢复默认路径

**Files:**
- Modify: `scripts/backup_db.sh`
- Modify: `scripts/restore_db.sh`
- Modify: `docs/快速试跑运维手册.md`
- Test: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [ ] **Step 1: 写失败测试，锁定快速试跑备份恢复默认 compose 叠加**

```python
def test_backup_and_restore_scripts_default_to_prod_overlay() -> None:
    backup = Path("scripts/backup_db.sh").read_text(encoding="utf-8")
    restore = Path("scripts/restore_db.sh").read_text(encoding="utf-8")

    assert 'COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"' in backup
    assert 'COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"' in restore
```

- [ ] **Step 2: 运行测试确认当前默认值仍只有单个 compose 文件**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_backup_and_restore_scripts_default_to_prod_overlay -q`

Expected: FAIL

- [ ] **Step 3: 最小修改备份与恢复脚本**

```sh
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"
SERVICE_NAME="${SERVICE_NAME:-db}"
```

- [ ] **Step 4: 在运维手册里补备份/恢复示例**

```md
## 备份
`./scripts/backup_db.sh`

## 恢复校验
`./scripts/restore_db.sh backups/postgres-YYYYMMDD-HHMMSS.dump`
```

- [ ] **Step 5: 重跑脚本 contract 测试**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_backup_and_restore_scripts_default_to_prod_overlay -q`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add scripts/backup_db.sh scripts/restore_db.sh docs/快速试跑运维手册.md backend/tests/test_quick_cloud_trial_docs_and_ops.py
git commit -m "chore: 收口快速试跑备份与恢复默认路径"
```

### Task 6: 执行 GitHub 接入与云端快速试跑

**Files:**
- Verify: `README.md`
- Verify: `docs/部署文档.md`
- Verify: `docs/快速试跑运维手册.md`

- [ ] **Step 1: 确认 GitHub 远端状态**

Run: `git remote -v`

Expected:
- 若已存在 `origin`，记录 URL 并继续
- 若不存在 `origin`，停止实现并向用户索取 GitHub 仓库 URL

- [ ] **Step 2: 如果缺少远端，用用户提供的 GitHub URL 绑定远端并推送**

Run: `git remote add origin <用户提供的 GitHub 仓库 URL>`

Expected: 无输出

Run: `git push -u origin main`

Expected: 当前分支成功推送到 GitHub

- [ ] **Step 3: 在云主机上准备部署目录**

Run:

```bash
mkdir -p /srv/aluminum-bypass
cd /srv/aluminum-bypass
git clone <用户提供的 GitHub 仓库 URL> .
```

Expected: 仓库成功拉取到云主机

- [ ] **Step 4: 生成并放置生产 `.env`**

Run:

```bash
python scripts/generate_env.py --app-env production --domain <已解析域名> --output .env
```

Expected: `.env` 生成成功，包含 `APP_ENV=production`

- [ ] **Step 5: 放置证书并部署**

Run:

```bash
mkdir -p ssl
./scripts/deploy_trial.sh
```

Expected:
- `docker compose ... config` 通过
- `docker compose ... up -d --build` 完成
- `docker compose ... ps` 显示 `db / backend / nginx` 正常

- [ ] **Step 6: 运行云端健康检查**

Run:

```bash
./scripts/check_trial_stack.sh https://<已解析域名>
```

Expected:
- `healthz` 200
- `readyz` 返回 `hard_gate_passed=true`

- [ ] **Step 7: 跑最小人工试跑**

Run:

```text
1. 管理员登录 /review/factory
2. 主操/机台账号提交一条数据
3. 专项 owner 提交一条补录
4. 管理员确认来源、状态和结果卡变化
```

Expected:
- 一个车间快速试跑闭环可用
- 无权限串看、串改

- [ ] **Step 8: 提交试跑收口改动并请求评审**

```bash
git status --short
git add README.md docs/部署文档.md docs/发布冻结基线清单.md docs/现场UAT清单.md docs/快速试跑运维手册.md .env.example scripts backend/tests .gitignore
git commit -m "feat: 收口 phase1 快速试跑上云路径"
```

然后使用 `@superpowers:requesting-code-review` 在进入真正上云前做一次发布前代码评审。

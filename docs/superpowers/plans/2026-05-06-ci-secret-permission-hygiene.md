# CI Secret And Permission Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 S08/S09：CI 不再写死测试口令/固定应用密钥，也不再用 `chmod 777` 放开 `backend/uploads`。

**Architecture:** 在 `compose-smoke` job 的 Prepare env 阶段生成一次性强随机 `SECRET_KEY` 和 `INIT_ADMIN_PASSWORD`，通过 `$GITHUB_ENV` 传给后续登录和 Playwright 步骤，并用 `::add-mask::` 避免日志泄漏。uploads 权限在 backend 镜像构建后按容器内 app 用户 UID/GID 创建为 `0770`，避免 world-writable。

**Tech Stack:** GitHub Actions YAML、Docker Compose、pytest 静态契约测试。

---

### Task 1: Lock CI Hygiene Contract

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Write the failing test**

Add a test reading `.github/workflows/ci.yml` and asserting:

```python
assert 'Round10CiAdmin!2026' not in source
assert 'ci-very-strong-secret-key-0123456789abcdef' not in source
assert 'chmod 777' not in source
assert 'openssl rand -hex 32' in source
assert 'CI_ADMIN_PASSWORD="CiAdmin-$(openssl rand -hex 12)!"' in source
assert '::add-mask::$CI_SECRET_KEY' in source
assert '::add-mask::$CI_ADMIN_PASSWORD' in source
assert 'PLAYWRIGHT_PASSWORD=$CI_ADMIN_PASSWORD' in source
assert 'docker compose build backend' in source
assert 'backend_uid="$(docker compose run --rm --no-deps --entrypoint id backend -u)"' in source
assert 'sudo install -d -m 0770 -o "$backend_uid" -g "$backend_gid" backend/uploads' in source
```

- [x] **Step 2: Verify red**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_ci_workflow_generates_ephemeral_secrets_and_scoped_upload_permissions -q`

Expected: FAIL because the workflow still contains fixed values and `chmod 777`.

Result: historical red completed before implementation; current guard passes and locks ephemeral CI secrets plus scoped upload permissions.

### Task 2: Generate CI Secrets At Runtime

**Files:**
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Remove fixed credential env values**

Keep `PLAYWRIGHT_BASE_URL`, but remove fixed `PLAYWRIGHT_USERNAME` / `PLAYWRIGHT_PASSWORD` from job-level env.

- [x] **Step 2: Generate values in Prepare env**

Inside `Prepare env`, add:

```bash
CI_SECRET_KEY="$(openssl rand -hex 32)"
CI_ADMIN_PASSWORD="CiAdmin-$(openssl rand -hex 12)!"
echo "::add-mask::$CI_SECRET_KEY"
echo "::add-mask::$CI_ADMIN_PASSWORD"
{
  echo "PLAYWRIGHT_USERNAME=admin"
  echo "PLAYWRIGHT_PASSWORD=$CI_ADMIN_PASSWORD"
} >> "$GITHUB_ENV"
```

Use those variables in `.env`:

```bash
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$CI_SECRET_KEY|" .env
sed -i "s|^INIT_ADMIN_PASSWORD=.*|INIT_ADMIN_PASSWORD=$CI_ADMIN_PASSWORD|" .env
```

Result: `.github/workflows/ci.yml` keeps only `PLAYWRIGHT_BASE_URL` in the compose-smoke job env, generates `CI_SECRET_KEY` and `CI_ADMIN_PASSWORD` in `Prepare env`, masks both values, exports Playwright credentials through `$GITHUB_ENV`, and writes the generated values into `.env`.

### Task 3: Scope Upload Permissions

**Files:**
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Remove world-writable setup**

Delete:

```bash
mkdir -p backend/uploads
chmod 777 backend/uploads
```

- [x] **Step 2: Add backend user permission step**

Add a step before `Start stack`:

```yaml
- name: Prepare backend upload permissions
  run: |
    docker compose build backend
    backend_uid="$(docker compose run --rm --no-deps --entrypoint id backend -u)"
    backend_gid="$(docker compose run --rm --no-deps --entrypoint id backend -g)"
    sudo install -d -m 0770 -o "$backend_uid" -g "$backend_gid" backend/uploads
```

- [x] **Step 3: Verify green**

Run: `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_ci_workflow_generates_ephemeral_secrets_and_scoped_upload_permissions -q`

Expected: PASS.

Result: `chmod 777` is absent; `Prepare backend upload permissions` builds the backend image, reads the backend container UID/GID, and creates `backend/uploads` with `0770` ownership scoped to that user/group.

### Task 4: Update Audit And Validate

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Add resolved audit rows**

Add `R69` for S08 and `R70` for S09.

- [x] **Step 2: Remove S08 and S09 from pending issues**

Delete both rows.

- [x] **Step 3: Run verification**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands exit 0; no whitespace errors.

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_ci_workflow_generates_ephemeral_secrets_and_scoped_upload_permissions -q` -> `1 passed`
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `30 passed, 1 deselected`
- `python -m pytest backend/tests/test_reference_command_center_spec.py backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q` -> `113 passed`
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected, 30 warnings`
- `git diff --check` -> pass

### Task 5: Commit And Push

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Add: `docs/superpowers/plans/2026-05-06-ci-secret-permission-hygiene.md`

- [x] **Step 1: Stage and check**

Run `git diff --cached --check` after staging.

- [x] **Step 2: Commit**

Run:

```powershell
git commit -m "ci: 生成临时密钥并收窄上传目录权限"
```

- [x] **Step 3: Push and confirm remote alignment**

Run:

```powershell
git push
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected: working tree clean and `HEAD` equals `origin/main`.

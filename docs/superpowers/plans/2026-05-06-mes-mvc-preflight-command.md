# MES MVC Preflight Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加一个安全的 MES MVC 预检命令，用于在不回显密钥的前提下判断生产配置是否齐全、登录页是否可达、以及在授权时登录链路是否可用。

**Architecture:** 新增独立脚本 `backend/scripts/check_mes_mvc_preflight.py`，不改变运行时服务和现有适配器行为。脚本复用 `Settings`，输出 JSON 或简短文本；测试通过 fake sender 覆盖缺配置、登录页 token、登录成功/失败。

**Tech Stack:** Python 3.10 + httpx + pytest；不新增依赖。

---

## Task 1: Tests

**Files:**
- Create: `backend/tests/test_mes_mvc_preflight_script.py`

- [x] **Step 1: Add missing-config test**

Assert `inspect_mes_mvc_preflight()` with `MES_ADAPTER=null` returns:
- `adapter='null'`
- `mvc_configured=False`
- missing env includes `MES_ADAPTER`, `MES_MVC_BASE_URL`, `MES_MVC_USERNAME`, `MES_MVC_PASSWORD`
- login page probe is skipped

- [x] **Step 2: Add login-page and optional-login tests**

Use a fake sender:
- login page response contains `__RequestVerificationToken`
- `attempt_login=False` does not send credentials
- `attempt_login=True` sends login requests through adapter and returns `login.status='success'`
- failure payload returns `login.status='failed'` without password values in `repr(payload)`

Run:
```powershell
python -m pytest backend/tests/test_mes_mvc_preflight_script.py -q
```

Result: FAIL before script existed; PASS after implementation.

## Task 2: Script

**Files:**
- Create: `backend/scripts/check_mes_mvc_preflight.py`

- [x] **Step 1: Implement safe inspection function**

Add `inspect_mes_mvc_preflight(runtime_settings=None, sender=None, attempt_login=False)` returning a dict with:
- `adapter`
- `mvc_configured`
- `missing_env`
- `login_page.status`: `skipped | reachable | failed`
- `login_page.token_present`
- `login.status`: `skipped | success | failed`

- [x] **Step 2: Add CLI**

Options:
- `--json`
- `--attempt-login`

Default text output must not print `MES_MVC_USERNAME`, `MES_MVC_PASSWORD`, API keys, or raw cookies.

## Task 3: Verification And Delivery

**Files:**
- Verify: backend test, existing MES adapter tests, docs gate

- [x] **Step 1: Focused tests**

Run:
```powershell
python -m pytest backend/tests/test_mes_mvc_preflight_script.py backend/tests/test_mvc_mes_adapter.py -q
```

- [ ] **Step 2: Docs/current-state update**

Record the command in `docs/deploy/current-state.md` only after running it on ECS.

- [ ] **Step 3: Commit, push, server fast-forward**

Commit with `feat: 增加 MES MVC 预检命令`, push, fast-forward `/srv/aluminum-bypass`, then run:
```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=. .venv/bin/python scripts/check_mes_mvc_preflight.py --json
```

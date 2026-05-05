# Playwright TLS Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 S11：Playwright 不再默认忽略所有 HTTPS 证书错误，只在本地自签名测试场景或显式环境变量下打开。

**Architecture:** 抽出一个纯函数 helper 判断 TLS 忽略范围，`playwright.config.js` 和显式创建的二级浏览器 context 共用它。用前端 node 单测覆盖本地/远端 URL 行为，并静态锁定全局配置不再写死 `ignoreHTTPSErrors: true`。

**Tech Stack:** Playwright config、JavaScript E2E helper、Node `node:test`。

---

### Task 1: Lock The TLS Scope Contract

**Files:**
- Add: `frontend/tests/playwrightTls.test.js`

- [ ] **Step 1: Write the failing test**

Add a test that imports `shouldIgnoreHttpsErrors` from `frontend/e2e/helpers/tls.js` and asserts:

```js
assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://localhost' }), true)
assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://127.0.0.1:4173' }), true)
assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'http://127.0.0.1:4173' }), false)
assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://mes.xintaily.com' }), false)
assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://mes.xintaily.com', allowInsecureTLS: '1' }), true)
```

Also read `frontend/playwright.config.js` and assert it uses `shouldIgnoreHttpsErrors` instead of hardcoded `ignoreHTTPSErrors: true`.

- [ ] **Step 2: Verify red**

Run: `npm run test -- playwrightTls.test.js`

Expected: FAIL because the helper file does not exist and config is still hardcoded.

### Task 2: Add Shared TLS Helper

**Files:**
- Add: `frontend/e2e/helpers/tls.js`

- [ ] **Step 1: Implement local HTTPS detection**

Add pure helpers:

```js
export function isLocalHttpsBaseURL(baseURL) {
  // true only for https://localhost, https://*.localhost, https://127.0.0.1, https://0.0.0.0, https://[::1]
}

export function shouldIgnoreHttpsErrors({ baseURL, allowInsecureTLS } = {}) {
  if (isTruthy(allowInsecureTLS)) return true
  return isLocalHttpsBaseURL(baseURL)
}
```

- [ ] **Step 2: Verify helper tests**

Run: `npm run test -- playwrightTls.test.js`

Expected: still fail until config imports the helper.

### Task 3: Use Helper In Playwright Contexts

**Files:**
- Modify: `frontend/playwright.config.js`
- Modify: `frontend/e2e/workshop-template-config.spec.js`
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js`

- [ ] **Step 1: Update global config**

Compute:

```js
const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'https://localhost'
```

Use:

```js
baseURL,
ignoreHTTPSErrors: shouldIgnoreHttpsErrors({ baseURL })
```

- [ ] **Step 2: Update explicit contexts**

For `browser.newContext(...)`, pass the configured `baseURL` and set `ignoreHTTPSErrors` through the same helper.

- [ ] **Step 3: Verify green**

Run: `npm run test -- playwrightTls.test.js`

Expected: PASS.

### Task 4: Update Audit And Validate

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Add resolved audit row**

Add `R68` under "已直接修复" describing S11.

- [ ] **Step 2: Remove S11 from pending issues**

Delete the `S11` row.

- [ ] **Step 3: Run verification**

Run:

```powershell
cd frontend; npm run test; npm run build
python -m pytest backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands exit 0; no whitespace errors.

### Task 5: Commit And Push

**Files:**
- Add: `frontend/tests/playwrightTls.test.js`
- Add: `frontend/e2e/helpers/tls.js`
- Modify: `frontend/playwright.config.js`
- Modify: `frontend/e2e/workshop-template-config.spec.js`
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Add: `docs/superpowers/plans/2026-05-06-playwright-tls-scope.md`

- [ ] **Step 1: Stage and check**

Run `git diff --cached --check` after staging.

- [ ] **Step 2: Commit**

Run:

```powershell
git commit -m "test: 收窄 playwright tls 忽略范围"
```

- [ ] **Step 3: Push and confirm remote alignment**

Run:

```powershell
git push
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected: working tree clean and `HEAD` equals `origin/main`.

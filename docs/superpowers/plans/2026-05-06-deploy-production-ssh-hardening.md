# Deploy Production SSH Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S01 by removing root/password/AutoAddPolicy from production and incremental deployment SSH scripts.

**Architecture:** Keep the existing Paramiko deployment flows, but require a least-privilege non-root SSH user, an explicit private key path, and a pinned `known_hosts` file. Use `sudo -n` only for remote operations that require privilege, so the deploy account can be scoped by server-side sudo policy.

**Tech Stack:** Python, Paramiko, pytest static/unit tests, Markdown audit ledger.

---

### Task 1: Add Red SSH Safety Tests

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Create: `docs/superpowers/plans/2026-05-06-deploy-production-ssh-hardening.md`

- [x] **Step 1: Add the static SSH guard**

Assert `deploy_production.py`:
- no longer references `DEPLOY_SSH_PASSWORD`
- requires `DEPLOY_SSH_KEY_PATH`
- requires `DEPLOY_KNOWN_HOSTS`
- uses `paramiko.RejectPolicy()`
- does not use `AutoAddPolicy`
- connects with `key_filename=ssh_key_path`
- disables agent and implicit key lookup
- requires a least-privilege non-root `DEPLOY_USER`

- [x] **Step 2: Add helper behavior tests**

Assert:
- missing `DEPLOY_USER` fails fast
- `DEPLOY_USER=root` fails fast
- unsafe usernames fail fast
- valid `DEPLOY_USER=deploy` passes
- missing `DEPLOY_KNOWN_HOSTS` path fails fast

- [x] **Step 3: Run the red tests**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_full_deploy_script_uses_key_based_known_hosts_non_root_ssh backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_full_deploy_script_rejects_missing_known_hosts_and_root_user -q
```

Expected: FAIL because the script still uses password auth, root default, and `AutoAddPolicy`.

Result: historical red completed before hardening; current static and helper behavior tests pass for key-based SSH, known_hosts, non-root deploy user, and missing-known-hosts failures.

### Task 2: Harden The Deployment Script

**Files:**
- Modify: `backend/scripts/deploy_production.py`
- Modify: `backend/scripts/deploy_zxtf_update.py`
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Replace password auth inputs**

Remove `DEPLOY_SSH_PASSWORD` from the script and require:
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY_PATH`
- `DEPLOY_KNOWN_HOSTS`

Keep existing runtime secret requirements for database URL, application secret, and initial admin password.

- [x] **Step 2: Pin host key verification**

Load `DEPLOY_KNOWN_HOSTS` into the Paramiko client and set `paramiko.RejectPolicy()`. Connect with `key_filename=ssh_key_path`, optional `DEPLOY_SSH_KEY_PASSPHRASE`, `allow_agent=False`, and `look_for_keys=False`.

- [x] **Step 3: Enforce non-root deploy user**

Add `require_deploy_user()` that rejects missing user, `root`, and shell-unsafe usernames. Use the returned user in `ssh.connect`.

- [x] **Step 4: Use explicit sudo for privileged remote actions**

Add `sudo_cmd(cmd)` using `DEPLOY_SUDO` defaulting to `sudo -n`. Wrap Docker cleanup, `/srv` setup, `/var/www/letsencrypt` setup, ownership changes, systemd, and nginx commands.

- [x] **Step 5: Install root-owned config files via sudo**

Add `sudo_install_file(...)` to upload a temp file by SFTP and move it into `/etc/systemd/system/` or `/etc/nginx/sites-enabled/` with `sudo install`.

- [x] **Step 6: Update legacy tests**

Update existing quick-cloud tests so they expect key-based SSH instead of password-based SSH.

- [x] **Step 7: Apply the same SSH boundary to the incremental deploy script**

Change `backend/scripts/deploy_zxtf_update.py` to use `ZXTF_DEPLOY_SSH_KEY_PATH`, `ZXTF_DEPLOY_KNOWN_HOSTS`, non-root `ZXTF_DEPLOY_USER`, `RejectPolicy`, and explicit `sudo -n` for privileged commands.

Result: `backend/scripts/deploy_production.py` and `backend/scripts/deploy_zxtf_update.py` no longer contain SSH password auth or `AutoAddPolicy`; both require key path, pinned known_hosts, safe non-root deploy user, `RejectPolicy`, `allow_agent=False`, and `look_for_keys=False`. Production deploy uses `sudo_cmd()` and `sudo_install_file()` for privileged actions and root-owned config files.

### Task 3: Update Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move S01 to resolved**

Add `R75` for SSH hardening and delete pending `S01`.

- [x] **Step 2: Run targeted tests**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
```

Expected: PASS.

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_full_deploy_script_uses_key_based_known_hosts_non_root_ssh backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_full_deploy_script_rejects_missing_known_hosts_and_root_user backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_incremental_deploy_script_uses_key_based_known_hosts_non_root_ssh -q` -> `3 passed`
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `30 passed, 1 deselected`

- [x] **Step 3: Run full checks**

Run:

```powershell
python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: PASS. Existing CRLF warnings are acceptable only if `git diff --check` exits 0.

Result:
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected, 30 warnings`
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass

- [x] **Step 4: Security self-review, commit, and push**

Review the diff for secret logging, host-key bypass, root usage, and shell injection. Commit:

Security self-review result: no new secrets or credential logging; no host-key bypass (`RejectPolicy` + loaded known_hosts); root SSH login rejected; deploy usernames are regex-validated before shell composition; privileged remote actions are routed through explicit `sudo -n` helpers.

```powershell
git add backend/scripts/deploy_production.py backend/scripts/deploy_zxtf_update.py backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-deploy-production-ssh-hardening.md
git commit -m "fix: 加固生产部署 SSH 登录"
git push
```

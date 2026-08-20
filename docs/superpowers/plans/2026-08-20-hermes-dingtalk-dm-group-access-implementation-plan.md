# Hermes DingTalk DM and Group Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Restrict DingTalk bot DMs to Zhang Zhaojia and both verified Meng Yujie accounts while allowing every organization member to use Hermes in any group only after a real @ mention.

**Architecture:** Add a DM-only allowlist at the DingTalk adapter edge in the trusted Hermes fork, before the gateway receives a private message. Keep the existing enterprise-wide gateway allowlist for groups, enforce structured mention gating, and persist the three stable DingTalk user IDs in Hermes `config.yaml` from both production deployment workflows.

**Tech Stack:** Python 3.11, NousResearch Hermes gateway plugins, pytest, YAML, GitHub Actions, systemd, DingTalk Stream, PowerShell/SSH production operations.

---

## File Map

Hermes fork `https://github.com/zhangzhaojia6-boop/hermes-agent.git`:

- Modify `plugins/platforms/dingtalk/adapter.py`: read and enforce `dm_allowed_users` only for direct messages.
- Modify `tests/gateway/test_dingtalk.py`: prove private and group behavior independently.

Data hub repository:

- Modify `.github/workflows/configure-dingtalk-stream-prod.yml`: persist the access policy during DingTalk credential apply and restore `config.yaml` on failure.
- Modify `.github/workflows/production-sync-status.yml`: persist the same policy during exact-SHA production deploy and restore it on rollback.
- Modify `backend/tests/test_production_workflow_contracts.py`: reject future workflow drift.
- Modify `docs/superpowers/specs/2026-08-20-hermes-dingtalk-dm-group-access-design.md`: retain the already-approved config location correction.

No database migration, new page, new robot, or new service is required.

### Task 1: Add DM-only authorization to the trusted Hermes fork

**Files:**
- Modify: `plugins/platforms/dingtalk/adapter.py:263-272,628-649,925-944`
- Test: `tests/gateway/test_dingtalk.py:1020-1120`

- [x] **Step 1: Create an isolated Hermes checkout at the trusted production baseline**

Run from the data hub repository root:

```powershell
git clone https://github.com/zhangzhaojia6-boop/hermes-agent.git .worktrees/hermes-dm-access
git -C .worktrees/hermes-dm-access checkout -b feat/dingtalk-dm-group-access d0f3ccef42d3d7c43085165c87ff373c1d3a3fb1
git -C .worktrees/hermes-dm-access status --short --branch
```

Expected: clean branch `feat/dingtalk-dm-group-access` at the exact production baseline.

- [x] **Step 2: Write failing adapter policy tests**

Add these tests under `TestAllowedUsersGate` in `tests/gateway/test_dingtalk.py`:

```python
    def test_dm_allowlist_accepts_configured_sender(self, monkeypatch):
        adapter = _make_gating_adapter(
            monkeypatch,
            extra={"allowed_users": ["*"], "dm_allowed_users": ["owner", "assistant"]},
        )
        assert adapter._is_dm_user_allowed("ignored", "owner") is True

    def test_dm_allowlist_rejects_unconfigured_sender(self, monkeypatch):
        adapter = _make_gating_adapter(
            monkeypatch,
            extra={"allowed_users": ["*"], "dm_allowed_users": ["owner", "assistant"]},
        )
        assert adapter._is_dm_user_allowed("other", "other-staff") is False

    def test_empty_dm_allowlist_fails_closed(self, monkeypatch):
        adapter = _make_gating_adapter(monkeypatch, extra={"allowed_users": ["*"]})
        assert adapter._is_dm_user_allowed("anyone", "any-staff") is False

    def test_group_policy_does_not_use_dm_allowlist(self, monkeypatch):
        adapter = _make_gating_adapter(
            monkeypatch,
            extra={
                "allowed_users": ["*"],
                "dm_allowed_users": ["owner", "assistant"],
                "require_mention": True,
            },
        )
        mentioned = SimpleNamespace(is_in_at_list=True)
        assert adapter._should_process_message(mentioned, "@机器人 查询产量", True, "group-any") is True
```

- [x] **Step 3: Run the focused tests and verify red**

Run:

```powershell
cd .worktrees/hermes-dm-access
uv run pytest tests/gateway/test_dingtalk.py::TestAllowedUsersGate -q
```

Expected: failures because `_is_dm_user_allowed` does not exist.

- [x] **Step 4: Implement the smallest adapter change**

Initialize the DM allowlist next to the existing global allowlist:

```python
        self._allowed_users: Set[str] = self._load_allowed_users()
        self._dm_allowed_users: Set[str] = self._load_dm_allowed_users()
```

Add the following methods after `_load_allowed_users`:

```python
    def _load_dm_allowed_users(self) -> Set[str]:
        raw = self.config.extra.get("dm_allowed_users") if self.config.extra else None
        if isinstance(raw, list):
            items = [str(part).strip() for part in raw if str(part).strip()]
        else:
            items = [part.strip() for part in str(raw or "").split(",") if part.strip()]
        return {item.lower() for item in items}

    def _is_dm_user_allowed(self, sender_id: str, sender_staff_id: str) -> bool:
        if not self._dm_allowed_users:
            return False
        candidates = {(sender_id or "").lower(), (sender_staff_id or "").lower()}
        candidates.discard("")
        return bool(candidates & self._dm_allowed_users)
```

Replace the current all-message allowlist block in `_on_message` with:

```python
        # The global allowlist protects the platform boundary. Private access
        # is narrower and fails closed when no explicit DM users are configured.
        if not self._is_user_allowed(sender_id, sender_staff_id):
            logger.debug(
                "[%s] Dropping message from non-allowlisted user staff_id=%s sender_id=%s",
                self.name, sender_staff_id, sender_id,
            )
            return
        if not is_group and not self._is_dm_user_allowed(sender_id, sender_staff_id):
            logger.debug("[%s] Dropping unauthorized direct message", self.name)
            return
```

Do not log the rejected sender IDs in the DM-specific line.

- [x] **Step 5: Run focused and adjacent Hermes tests**

Run:

```powershell
uv run pytest tests/gateway/test_dingtalk.py::TestAllowedUsersGate -q
uv run pytest tests/gateway/test_dingtalk.py -q
```

Expected: all tests pass.

- [x] **Step 6: Commit and publish the trusted Hermes change**

```powershell
git add plugins/platforms/dingtalk/adapter.py tests/gateway/test_dingtalk.py
git commit -m "fix(dingtalk): separate DM and group authorization"
git push origin HEAD:main
git rev-parse HEAD
```

Expected: the fork's `main` advances from `d0f3ccef...`; save the resulting full SHA as `HERMES_ACCESS_SHA`.

### Task 2: Persist the policy in both production workflows

**Files:**
- Modify: `.github/workflows/configure-dingtalk-stream-prod.yml`
- Modify: `.github/workflows/production-sync-status.yml`
- Test: `backend/tests/test_production_workflow_contracts.py`

- [x] **Step 1: Write failing workflow contract assertions**

Add shared expected IDs and assertions to the existing DingTalk workflow tests:

```python
dm_user_ids = (
    "666327013924069283",
    "076765530923422118",
    "081323311123422118",
)
for user_id in dm_user_ids:
    assert user_id in source
assert 'extra["dm_allowed_users"] = dm_allowed_users' in source
assert 'extra["require_mention"] = True' in source
assert 'extra["allowed_chats"] = []' in source
assert 'extra["free_response_chats"] = []' in source
assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_ALLOWED_USERS" "*"' in source
assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_REQUIRE_MENTION" "false"' not in source
```

Apply equivalent assertions to both `configure-dingtalk-stream-prod.yml` and `production-sync-status.yml` contract tests.

- [x] **Step 2: Run the contract tests and verify red**

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_production_workflow_contracts.py -q
```

Expected: failures for missing DM IDs/config writes and the existing `require_mention=false` assignment.

- [x] **Step 3: Add one identical config writer to each workflow**

Define the non-secret stable identity list near each remote script's constants:

```bash
HERMES_DM_ALLOWED_USERS="666327013924069283,076765530923422118,081323311123422118"
HERMES_CONFIG_FILE="$HERMES_HOME/config.yaml"
```

Add a helper that runs with the active Hermes runtime Python:

```bash
configure_hermes_dingtalk_access() {
  local runtime_python="$1"
  HERMES_HOME="$HERMES_HOME" "$runtime_python" -P - "$HERMES_DM_ALLOWED_USERS" <<'PY'
import sys

from hermes_cli.config import get_config_path, read_raw_config, require_readable_config_before_write
from utils import atomic_yaml_write

dm_allowed_users = [item.strip() for item in sys.argv[1].split(",") if item.strip()]
if len(dm_allowed_users) != 3 or len(set(dm_allowed_users)) != 3:
    raise SystemExit("invalid DingTalk DM allowlist")

config_path = get_config_path()
require_readable_config_before_write(config_path)
config = read_raw_config()
platforms = config.get("platforms")
platforms = dict(platforms) if isinstance(platforms, dict) else {}
dingtalk = platforms.get("dingtalk")
dingtalk = dict(dingtalk) if isinstance(dingtalk, dict) else {}
extra = dingtalk.get("extra")
extra = dict(extra) if isinstance(extra, dict) else {}
extra["dm_allowed_users"] = dm_allowed_users
extra["require_mention"] = True
extra["allowed_chats"] = []
extra["free_response_chats"] = []
dingtalk["extra"] = extra
platforms["dingtalk"] = dingtalk
config["platforms"] = platforms
atomic_yaml_write(config_path, config, sort_keys=False)
print("HERMES_DINGTALK_ACCESS_CONFIGURED=yes")
PY
}
```

Call it after the runtime Python is resolved and before restarting Hermes. Keep `DINGTALK_ALLOWED_USERS=*`; remove or change every managed `DINGTALK_REQUIRE_MENTION=false` assignment to `true` so an environment override cannot defeat YAML.

- [x] **Step 4: Extend backup and rollback to cover `config.yaml`**

In each workflow, copy `HERMES_CONFIG_FILE` into the existing mode-700 backup directory before any write. On failure, atomically restore the config backup before restarting Hermes. Assert the backup exists and preserve owner/mode from the original file.

Use explicit state markers:

```bash
echo "HERMES_CONFIG_BACKUP_CREATED=yes"
echo "HERMES_CONFIG_ROLLBACK_RESTORED=yes"
```

- [x] **Step 5: Add a redacted status verifier**

Read `config.yaml` with the Hermes runtime and emit only:

```text
HERMES_DM_ALLOWED_USER_COUNT=3
HERMES_DM_ALLOWED_USERS_MATCH=yes
HERMES_GROUP_REQUIRE_MENTION=yes
HERMES_GROUP_SCOPE=all_application_groups
```

The verifier must compare a set of IDs but must not print the IDs or config contents.

- [x] **Step 6: Run data hub workflow tests**

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_production_workflow_contracts.py -q
python -c "import pathlib,yaml; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('.github/workflows/configure-dingtalk-stream-prod.yml','.github/workflows/production-sync-status.yml')]; print('YAML_OK')"
git diff --check
```

Expected: all tests pass, `YAML_OK`, and no whitespace errors.

- [x] **Step 7: Commit and push the data hub workflow change**

```powershell
git add .github/workflows/configure-dingtalk-stream-prod.yml .github/workflows/production-sync-status.yml backend/tests/test_production_workflow_contracts.py docs/superpowers/specs/2026-08-20-hermes-dingtalk-dm-group-access-design.md
git commit -m "fix(hermes): enforce DingTalk DM and group access"
git push origin main
git rev-parse HEAD
```

Save the full SHA as `DATAHUB_ACCESS_SHA`.

### Task 3: Deploy both exact trusted SHAs with rollback protection

**Files:**
- Runtime: `/srv/hermes-cloud/runtime/.hermes/hermes-agent`
- Runtime config: `/srv/hermes-cloud/runtime/.hermes/config.yaml`
- Runtime service: `hermes-gateway.service`

- [x] **Step 1: Run pre-deploy read-only checks**

```powershell
ssh root@8.140.218.13 'cd /srv/aluminum-bypass && git status --short --branch && git rev-parse HEAD; cd /srv/hermes-cloud/runtime/.hermes/hermes-agent && git status --short --branch && git rev-parse HEAD; systemctl is-active aluminum-bypass hermes-gateway; curl -fsS http://127.0.0.1:8000/readyz >/dev/null'
```

Expected: tracked worktrees clean, both services active, readiness succeeds.

- [x] **Step 2: Dispatch the existing exact-SHA production workflow**

```powershell
gh workflow run production-sync-status.yml --ref main -f confirm=prod-sync -f mode=deploy -f datahub_sha=$DATAHUB_ACCESS_SHA -f hermes_sha=$HERMES_ACCESS_SHA
gh run watch --exit-status
```

Expected workflow markers:

```text
HERMES_CONFIG_BACKUP_CREATED=yes
HERMES_DINGTALK_ACCESS_CONFIGURED=yes
HERMES_DM_ALLOWED_USERS_MATCH=yes
DINGTALK_STREAM_CONNECTION=connected
GO_LIVE_READY=true
```

- [x] **Step 3: Verify repository and service synchronization**

Confirm local data hub, `origin/main`, production data hub, fork `main`, and production Hermes resolve to the two saved SHAs. Confirm both production worktrees have no tracked changes.

### Task 4: Run the four-path production authorization gate

**Files:**
- Test runtime only; do not persist synthetic messages.

- [x] **Step 1: Run a production-runtime synthetic adapter gate**

Use the active Hermes runtime Python and `PlatformConfig` to instantiate the real production adapter config, then assert:

```python
assert adapter._is_dm_user_allowed("", "666327013924069283")
assert adapter._is_dm_user_allowed("", "076765530923422118")
assert adapter._is_dm_user_allowed("", "081323311123422118")
assert not adapter._is_dm_user_allowed("", "unauthorized-user")
assert adapter._should_process_message(mentioned_message, "查询产量", True, "any-group")
assert not adapter._should_process_message(unmentioned_message, "查询产量", True, "any-group")
```

Expected: `HERMES_DINGTALK_ACCESS_SYNTHETIC_GATE=pass`.

- [x] **Step 2: Verify production runtime health**

Check:

```text
hermes-gateway=active
aluminum-bypass=active
DingTalk Stream=connected
/healthz=ok
/readyz=ready
MES sync=ok
current Hermes PID has no APIConnectionError or AccountOverdueError
```

Run the data hub actor classifier with production settings and assert that Zhang
Zhaojia's `userid` yields `is_root_owner=True`, while both Meng Yujie IDs yield
`is_root_owner=False`. This check must not mutate users or authorization data.

- [x] **Step 3: Re-run Luna and forced Sol failover probes**

Run the existing Chinese identity inference against `gpt-5.6-luna`, then force an invalid primary model and require the configured `gpt-5.6-sol` fallback to answer. Do not send these probes to DingTalk users.

- [x] **Step 4: Record the final production evidence**

Update the plan checkboxes and report only redacted counts/statuses. Never print credentials, proxy values, auth tokens, full DingTalk payloads, or rejected user identifiers in logs.

## Completion Gate

The task is complete only when all of the following are true:

- Hermes fork and data hub `main` contain the reviewed commits.
- Production runs those exact trusted SHAs with clean tracked worktrees.
- Three DM IDs match; an unknown DM ID fails closed.
- Any group can use Hermes only through a structured @ mention.
- Zhang Zhaojia remains root owner; Meng Yujie remains a normal private-chat user.
- DingTalk Stream, data hub, MES readiness, Luna, and Sol failover are all healthy.

## Execution Evidence

Completed on 2026-08-20:

- Hermes fork SHA: `4d4452067cb43ebcd437eba78b0c67d9f1c64652`.
- Data hub deployment SHA: `2df5671c8fde0d0702fa3c6564b4996a5df0166c`.
- GitHub Actions production run: `32348766035`, conclusion `success`.
- Hermes DingTalk adapter tests: `83 passed`.
- Data hub production workflow contract tests: `52 passed`.
- Production access gate: `HERMES_DINGTALK_ACCESS_SYNTHETIC_GATE=pass`.
- Production root-owner gate: `HERMES_ROOT_OWNER_CLASSIFICATION=pass`.
- Production configuration: DM count `3`, exact match `yes`, group mention required `yes`, group scope `all_application_groups`.
- Runtime health: data hub and Hermes `active`, DingTalk Stream `connected`, `/readyz=ready`, MES sync and pipeline `ok`.
- Model health: Luna primary inference passed; forced invalid primary successfully failed over to Sol.

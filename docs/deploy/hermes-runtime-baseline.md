# Hermes Runtime Baseline

Capture time: `2026-07-11T04:44:26Z`

## Data Hub

- Branch: `feature/hermes-single-ingress-fact-closure`
- Baseline document parent SHA: `722b718cee7586779415dd2a43d0356a7de6a3bf`
- `origin/main`: `51bccce1c30b76be4045f0889a490183ad2d8638`

## Production Hermes

- Repository: `/srv/hermes-cloud/runtime/.hermes/hermes-agent`
- Remote: `origin` -> `https://github.com/NousResearch/hermes-agent.git`
- Branch before capture: `main`
- SHA before capture: `1cec910b6a064d4e4821930be5cfaaf6145a2afd`
- Baseline branch: `feature/xintai-single-ingress-fact-closure`
- SHA after baseline commit: `2b9629b0d6c854b9ed6869ffc4e4ce2120c4a27e`
- Baseline commit: `chore: capture Xintai Hermes production baseline`
- Service state capture time: `2026-07-11T04:54:43Z`
- `hermes-gateway.service`: `active/running` (active since `2026-07-09 16:45:35 CST`)
- `hermes-feishu-webhook.service`: `active/running` (active since `2026-06-05 00:08:43 CST`)

The baseline commit contains only these tracked files:

- `gateway/platforms/dingtalk.py`
- `gateway/platforms/feishu.py`
- `gateway/run.py`
- `package-lock.json`
- `uv.lock`

## Reversible Backup

- Directory: `/var/backups/xintai-hermes/20260711T044426Z`
- Bundle: `/var/backups/xintai-hermes/20260711T044426Z/repository.bundle`
- `git bundle verify`: passed; the bundle contains complete repository history.
- Archive permissions: directory `700`; files `600`.
- Captured artifacts: binary working-tree patch, porcelain v2 status, full repository bundle, untracked-file manifest, and backup-file manifest.

Before the baseline commit, the repository had 34 modified tracked files, 23 untracked files, and 17 backup-like files. After the commit, 29 modified tracked files, 23 untracked files, and 17 backup-like files remain untouched. The staging area is empty.

## Safety Checks

- The staged path allowlist and `git diff --cached --check` passed.
- Secret-value and credential-URL scans reported no matches.
- The staged Python files passed AST parsing; `package-lock.json` and `uv.lock` passed JSON and TOML parsing.
- No environment files, credentials, caches, logs, chat data, backup files, virtual environments, or `node_modules` were staged.
- No files were deleted, no remote was pushed, and no service was restarted or otherwise changed.

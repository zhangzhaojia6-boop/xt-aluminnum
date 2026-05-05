# Launch Readiness AI Assistant Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `docs/launch-readiness-checklist.md` with the current AI assistant runtime surface and fallback truthfulness rules.

**Architecture:** Documentation-only correction with a backend doc-contract test. Do not change routes or frontend behavior. The checklist should use `AI 助手` and `/manage/ai-assistant`, not the retired `AI 大脑` / `Brain Center` labels.

**Tech Stack:** pytest doc-contract tests, Markdown docs.

---

### Task 1: Lock Launch Readiness AI Runtime Naming

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Add red doc-contract test**

Assert `docs/launch-readiness-checklist.md`:

- does not contain `AI 大脑` or `Brain Center`
- does contain `AI 助手`
- does contain `/manage/ai-assistant`

Also assert `frontend/src/router/index.js` still routes `factory-ai-assistant` to `AiWorkstation`.

- [x] **Step 2: Run red test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_launch_readiness_uses_current_ai_assistant_runtime_name -q
```

Expected: fail because the checklist still contains old AI naming.

Result before implementation: FAIL, `AI 大脑中心` remained in `docs/launch-readiness-checklist.md`.

### Task 2: Refresh Launch Readiness Checklist

**Files:**
- Modify: `docs/launch-readiness-checklist.md`

- [x] **Step 1: Replace retired AI naming**

Replace `AI 大脑中心` / `Brain Center` with `AI 助手` and `/manage/ai-assistant`.

- [x] **Step 2: Note fallback truthfulness**

Keep the checklist concise, but state that AI capability state must display connected/unconnected truthfully.

- [x] **Step 3: Run green target test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_launch_readiness_uses_current_ai_assistant_runtime_name -q
```

Expected: pass.

Result after implementation: PASS, `1 passed`.

### Task 3: Verify and Close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-launch-readiness-ai-assistant-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all pass.

Verification results:

- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`: PASS, `28 passed, 1 deselected`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `649 passed, 119 deselected, 30 warnings`.
- `git diff --check`: PASS.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/launch-readiness-checklist.md docs/superpowers/plans/2026-05-06-launch-readiness-ai-assistant-truthfulness.md
git commit -m "docs: 标清上线清单 AI 助手口径"
git push
```

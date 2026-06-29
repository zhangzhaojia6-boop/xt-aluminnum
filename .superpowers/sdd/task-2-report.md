status: DONE

task: Task 2 - Hermes 20 question real-run snapshot runner

changed files:
- backend/app/services/hermes_20_question_runner.py
- backend/tests/test_hermes_20_question_runner.py

commits:
- `d9b88e15` feat: add hermes 20 question acceptance runner

implementation:
- Added `run_20_question_acceptance()` to execute the 20-question catalog through the existing `run_root_owner_production_turn()` API.
- Added `DingTalkDeliveryTarget` for approved DingTalk delivery targets.
- Added snapshot construction from existing `AgentRun`, `AgentOutboxMessage`, and `ExternalMessageLog` rows.
- Added approved target dispatch through the existing `agent_communication_service` register, bind, queue, dispatch, and log APIs.
- Aggregated approved target dispatch results into the acceptance snapshot `dispatch` payload as `target_results`, `delivery_sent_count`, and `delivery_target_count`.
- Added the runner test from the task brief; it fakes the production turn and uses local database rows, so it does not call real DingTalk.

TDD evidence:
- RED:
  - command: `cd backend; python -m pytest -q tests/test_hermes_20_question_runner.py`
  - result: failed as expected
  - key output: `ModuleNotFoundError: No module named 'app.services.hermes_20_question_runner'`
- GREEN:
  - command: `cd backend; python -m pytest -q tests/test_hermes_20_question_runner.py`
  - result: passed
  - key output: `1 passed in 3.41s`

verification:
- `cd backend; python -m compileall app/services/hermes_20_question_runner.py`
  - output: command exited 0 with no stdout
- `cd backend; python -m pytest -q tests/test_hermes_20_question_acceptance.py tests/test_hermes_20_question_runner.py`
  - output: `ERROR: file or directory not found: tests/test_hermes_20_question_acceptance.py`
  - note: this was an accidental probe for a non-existent Task 1 filename; no tests ran.
- `cd backend; python -m pytest -q tests/test_hermes_20_question_real_acceptance.py tests/test_hermes_20_question_runner.py`
  - output: `13 passed in 3.27s`
- `cd backend; python -m pytest -q tests/test_hermes_20_question_runner.py`
  - output: `1 passed in 3.17s`
- `git diff --check -- backend/app/services/hermes_20_question_runner.py backend/tests/test_hermes_20_question_runner.py`
  - output: command exited 0 with no stdout

self-review:
- Scope stayed limited to the requested runner service, runner test, and this task report.
- The runner uses the existing production turn API and existing agent communication APIs; it does not add routers, CLI, frontend, migrations, or new delivery plumbing.
- Tests do not call real DingTalk; dispatch is avoided in the brief test by passing no `delivery_targets`.
- The runner treats delivery targets as explicit approved targets only; without targets it only snapshots the turn's existing outbox/log result.
- Existing dirty worktree changes were not reverted or staged.

concerns:
- The brief-provided test covers snapshot creation from existing turn outputs. The new target dispatch path is implemented from the corrected brief code, but not separately exercised by an added test beyond the existing acceptance/import coverage.
- The report file had pre-existing content from another task and was overwritten because this task explicitly required a full report here.

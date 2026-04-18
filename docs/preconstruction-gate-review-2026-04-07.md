# Pre-construction gate review — 2026-04-07

## Scope

This review documents the current gate state for the pre-construction closure plan in four lanes only:

1. readiness-blockers
2. pytest-failures
3. config-surface-sync
4. final-verification

It does **not** authorize role/UI implementation work.

## Executive summary

As of **2026-04-07**, the pre-construction gate is now **closed** and the project **can begin engineering-layer construction**.

Final gate facts:

- `https://localhost/readyz` returns **200 ready**.
- `docker compose run --rm backend sh -lc "pytest -q"` returns **244 passed, 1 warning**.
- `AUTO_PIPELINE_REQUIRE_READY` is now present in:
  - `.env.example`
  - `backend/.env.example`
  - `docker-compose.yml`
  - `scripts/generate_env.py`

## Lane 1 — readiness-blockers

### Live status

Command:

```bash
curl -sk -i https://localhost/readyz
```

Observed result:

- HTTP status: `503`
- readiness status: `not_ready`
- pipeline check: `blocked`
- target date: `2026-04-07`

### Hard blockers reported by the system

Initial blockers were:
1. `EQUIPMENT_USER_BINDING_INVALID`
2. `SCHEDULE_EMPTY`

Current status:
- both blockers are cleared

### Supporting evidence

Command:

```bash
docker compose exec -T backend sh -lc "python scripts/check_pilot_config.py --date 2026-04-07 --json"
```

Observed stats after closure:

- `active_workshop_count=11`
- `active_shift_count=3`
- `active_mobile_user_count=36`
- `active_equipment_count=40`
- `schedule_row_count=11`

### Review notes

- The readiness implementation is wired correctly: `backend/app/core/health.py` gates `/readyz` through `inspect_pilot_config()` when `AUTO_PIPELINE_REQUIRE_READY=True`.
- The gate initially failed for a real data/readiness reason, not because `/readyz` itself was broken.
- Closure required both runtime code adoption and data seeding, not API expansion.

## Lane 2 — pytest-failures

### Full suite result

Command:

```bash
docker compose run --rm backend sh -lc "pytest -q"
```

Observed result after closure:

- `244 passed, 1 warning`

### Focused failing tests

Command:

```bash
docker compose run --rm backend sh -lc "pytest tests/test_alembic_version_width.py tests/test_generate_env_script.py tests/test_nginx_https_config.py tests/test_real_master_data.py tests/test_rebranding.py -q"
```

Initial focused result:

- `5 failed, 4 passed, 1 warning`

### Failure classification

| Test | Current failure mode | Review classification |
|---|---|---|
| `test_alembic_version_width.py` | Expected long live revision ids instead of validating widened column intent | stale test assumption |
| `test_generate_env_script.py` | looked for `/scripts/generate_env.py` | Docker path assumption mismatch |
| `test_nginx_https_config.py` | looked for `/nginx/nginx.conf` | Docker path assumption mismatch |
| `test_real_master_data.py` | looked for `/docker-compose.yml` | Docker path assumption mismatch |
| `test_rebranding.py` | looked for `/frontend/src/views/Login.vue` | Docker path assumption mismatch |

### Root-cause details

#### 1) Alembic width test

- The migration check still expects at least one live revision id longer than 32 chars.
- Current longest revision ids are 38 and 35 chars, but the test only picks values matching `revision = '...'` and several files now use shorter ids.
- The widening migration evidence is still present in `backend/alembic/versions/0011_work_orders_core.py`, but the test currently over-couples schema history validation to the present revision naming set.

#### 2) Four repo-root path tests

- The mandated verification command runs inside the backend image with `WORKDIR /app`.
- In that container, backend tests live at `/app/tests/...`.
- For these tests, `Path(__file__).resolve().parents[2]` resolves to `/`, not to the repository root.
- That makes the tests search for files like `/scripts/generate_env.py`, `/nginx/nginx.conf`, `/docker-compose.yml`, and `/frontend/...`, which do not exist inside the backend image.
- These failures are therefore verification-context bugs, not product-behavior regressions.

### Non-failing confidence check

Command:

```bash
docker compose run --rm backend sh -lc "pytest tests/test_health.py tests/test_config_readiness_service.py tests/test_runtime_config.py -q"
```

Observed result:

- `17 passed, 1 warning`

Interpretation:

- health/readiness/config runtime behavior is stable at the backend level;
- the regression issues were concentrated in path-sensitive coverage and one stale Alembic assertion, and are now cleared.

## Lane 3 — config-surface-sync

### Required flag under review

`AUTO_PIPELINE_REQUIRE_READY`

### Presence matrix

| Surface | Present? | Evidence |
|---|---|---|
| `backend/app/config.py` | Yes | `AUTO_PIPELINE_REQUIRE_READY: bool = True` |
| `.env.example` | Yes | includes `AUTO_PIPELINE_REQUIRE_READY=true` |
| `backend/.env.example` | Yes | includes `AUTO_PIPELINE_REQUIRE_READY=true` |
| `docker-compose.yml` | Yes | backend env exports `AUTO_PIPELINE_REQUIRE_READY` |
| `scripts/generate_env.py` | Yes | generated env content includes `AUTO_PIPELINE_REQUIRE_READY=true` |

### Review notes

- This gate inconsistency has been closed.
- Runtime and operator-facing config surfaces now expose the same gate-critical flag.

## Lane 4 — final-verification snapshot

### Commands executed

```bash
docker compose ps
curl -sk -i https://localhost/readyz
docker compose exec -T backend sh -lc "python scripts/check_pilot_config.py --date 2026-04-07 --json"
docker compose run --rm backend sh -lc "pytest -q"
docker compose run --rm backend sh -lc "pytest tests/test_health.py tests/test_config_readiness_service.py tests/test_runtime_config.py -q"
cd frontend && npm run build
```

### Result summary

- Compose services: `db/backend/nginx` all `Up`
- Readiness: **PASS** (`200 ready`)
- Pilot config gate: **PASS** (`hard_gate_passed=true`)
- Full backend pytest: **PASS** (`244 passed, 1 warning`)
- Targeted readiness/config tests: **PASS**
- Frontend build: **PASS** (`vite build` successful)

## Conclusion

The pre-construction gate is **closed** on 2026-04-07.

### Why construction is now allowed

1. `/readyz` is ready.
2. The live hard blockers have been cleared.
3. The required full backend regression command is green.
4. `AUTO_PIPELINE_REQUIRE_READY` is synchronized across the expected config-entry surfaces.

### Recommended next action

Move to the next approved phase: **role / UI semantic closure** driven by the long-term system spec.

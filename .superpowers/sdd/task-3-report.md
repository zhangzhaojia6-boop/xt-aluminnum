status: DONE

changed files:
- backend/app/services/hermes_factory_normalization_service.py
- backend/tests/test_hermes_factory_normalization_service.py
- .superpowers/sdd/task-3-report.md

commit:
- b17da27e Normalize factory-brain requests into routing-ready facts

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `ERROR collecting tests/test_hermes_factory_normalization_service.py`
    - `ModuleNotFoundError: No module named 'app.services.hermes_factory_normalization_service'`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `2 passed in 2.24s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output: success
- `git diff --check`
  - output: success

self-review:
- 按 brief 先写测试，再运行红灯，确认失败原因就是缺少 normalization service。
- 实现严格按 Task 3 范围收口，只新增 normalization service 和对应测试，没有改动意图分类器、orchestrator 或其他旧行为。
- 归一化规则保持最小：统一车间别名、统一指标列表、固定数据源优先级、判断 artifact 与输出模式。

concerns:
- `docs/longterm-ai-skill-system-spec.md` 在当前 worktree 中不存在；本次改读了仓库里实际存在的相关 Hermes 设计文档，不影响 Task 3 落地。

## Fix Task 3 Review Finding

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

commit:
- `2acdac72` Recognize bare workshop numbers in factory normalization

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 2 passed in 3.17s`
    - failures: bare `1650` / `1850` / `2050` natural-language cases normalized to `factory` instead of `workshop`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `5 passed in 2.17s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'app/services/hermes_factory_normalization_service.py'...`
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`

## Fix Task 3 Final Review Finding

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 5 passed in 3.62s`
    - failures: `entities={'workshop': '1650'/'1850'/'2050'}` still normalized to `factory` when text did not include the workshop number
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `8 passed in 2.11s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`
- `git diff --check -- backend/app/services/hermes_factory_normalization_service.py backend/tests/test_hermes_factory_normalization_service.py .superpowers/sdd/task-3-report.md`
  - output: success

self-review:
- 只补了一个缺口：当上游意图分类器把车间直接归一成裸数字字符串时，归一化层现在会把它当作车间，不再错误回退到全厂。
- 原有别名匹配、文本裸数字匹配、指标归一化和输出模式逻辑都保持不变。

## Fix Task 3 Final Review Finding Round 2

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `1 failed, 11 passed in 2.55s`
    - failure: `今天产量2050吨发我` was still normalized to `workshop` instead of `factory`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `12 passed in 2.21s`

self-review:
- 这次只收紧了“文本里裸数字车间号”的识别条件，不动实体兜底、别名映射、指标归一化和输出模式。
- 现在只有两种文本会按裸数字识别车间：句首车间号上下文，或数字后面明确跟 `车间`、`冷轧`、`机组`。
- `今天产量2050吨发我` 这种吨数表达会留在全厂范围，不会再误命中 `2050` 车间。

## Fix Task 3 Reviewer Finding: Full Workshop Entity Aliases

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 12 passed in 2.67s`
    - failures: `entities={'workshop': '1650冷轧车间'/'1850冷轧车间'/'2050冷轧车间'}` still normalized to `factory` when text did not include the workshop
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `15 passed in 2.12s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`
- `git diff --check -- backend/app/services/hermes_factory_normalization_service.py backend/tests/test_hermes_factory_normalization_service.py .superpowers/sdd/task-3-report.md`
  - output: success

self-review:
- 这次只补了 3 个完整车间实体别名：`1650冷轧车间`、`1850冷轧车间`、`2050冷轧车间`。
- 没有放宽数字识别规则，所以 `今天产量2050吨发我` 仍然会保持全厂范围，不会被错判成 `2050` 车间。

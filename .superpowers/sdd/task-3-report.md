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

# Task 4 Report: CLI for approved real acceptance runs

## Status

DONE

## Changed Files

- `backend/scripts/hermes_20_question_acceptance.py`
- `backend/tests/test_hermes_20_question_runner.py`

## What Changed

新增 `backend/scripts/hermes_20_question_acceptance.py`，只做 Task 4 要求的最小 CLI 封装：

1. 提供 `parse_args()`。
2. 提供 `parse_delivery_targets()`，返回 `DingTalkDeliveryTarget`。
3. 默认安全：不带 `--real-delivery` 时，`args.real_delivery` 为 `False`，`main()` 直接拒绝真实验收。
4. `--target` 只接受 `dingtalk_group:key` 或 `dingtalk_work_notice:key`，并复用 runner 的白名单常量保持一致。
5. CLI 只调用现有 `run_20_question_acceptance()` 和 `render_acceptance_report()`，没有新增直接调用钉钉发送接口的逻辑。

同时在 `backend/tests/test_hermes_20_question_runner.py` 追加了 2 个 parser/target 解析测试。

说明：

- brief 里的示例导入路径是 `backend.scripts...`，但当前仓库现有脚本测试都用 `scripts...`。
- 这次按仓库当前接口改成 `from scripts.hermes_20_question_acceptance ...`，功能语义不变。

## Verification

### Red

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py::test_acceptance_cli_requires_explicit_real_delivery_flag tests/test_hermes_20_question_runner.py::test_acceptance_cli_parses_real_delivery_targets
```

结果：先失败，符合 TDD 红灯预期。

```text
ModuleNotFoundError: No module named 'scripts.hermes_20_question_acceptance'
```

### Green: parser tests

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py::test_acceptance_cli_requires_explicit_real_delivery_flag tests/test_hermes_20_question_runner.py::test_acceptance_cli_parses_real_delivery_targets
```

结果：

```text
2 passed in 2.76s
```

### Green: full requested suite

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py tests/test_hermes_20_question_real_acceptance.py tests/test_hermes_real_dingtalk_delivery_gate.py
```

结果：

```text
22 passed in 3.69s
```

### Compile

```powershell
cd backend
python -m compileall scripts/hermes_20_question_acceptance.py tests/test_hermes_20_question_runner.py
```

结果：退出码 0，通过。

```text
Compiling 'tests/test_hermes_20_question_runner.py'...
```

## Self Check

- 只改了允许范围内的代码文件和报告文件。
- 没有修改 `backend/app/services/hermes_20_question_runner.py`。
- 没有在测试里真实调用钉钉。
- 没有回滚工作区里其它人的改动。
- commit 只应包含：
  - `backend/scripts/hermes_20_question_acceptance.py`
  - `backend/tests/test_hermes_20_question_runner.py`

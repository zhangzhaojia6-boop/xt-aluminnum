status: DONE

changed files:
- backend/app/services/hermes_factory_brain_intent_service.py
- backend/tests/test_hermes_factory_brain_intent_service.py

commits:
- 6e0a317a Route common factory questions before model fallback

tests run with outputs:
- `cd backend && pytest tests/test_hermes_factory_brain_intent_service.py -q`
  - output: `pytest` not in PATH on this machine, command failed with `pytest : The term 'pytest' is not recognized...`
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py -q` (red step)
  - output:
    - `2 failed, 6 passed in 2.73s`
    - failed cases:
      - `test_common_business_phrases_route_before_model_fallback`
      - `test_non_business_question_uses_general_answer_lane`
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py -q` (green step)
  - output: `8 passed in 2.16s`
- `python -m compileall backend/app/services/hermes_factory_brain_intent_service.py`
  - output: success
- `git diff --check -- backend/app/services/hermes_factory_brain_intent_service.py backend/tests/test_hermes_factory_brain_intent_service.py`
  - output: success

self-review:
- 按 brief 先加测试、先看红灯，再补最小规则，没有提前改生产代码。
- 新增规则顺序按“更具体优先”处理，保证 `合同余量` 不再落到通用合同问题，`库存` 不再落到旧的 operations 分支。
- 保留了旧测试行为：`随便聊两句` 仍走原来的通用 fallback；`2050 今天电耗为什么高？` 仍保留旧的异常分析语义。
- 新增了显式非业务闲聊通道：命中 `笑话 / 闲聊 / 讲个` 时，返回 `should_use_factory_brain=False`，满足 Task 2 新要求。

concerns:
- `docs/longterm-ai-skill-system-spec.md` 在当前 worktree 中不存在；本次已改读 Task 2 直接相关的 `docs/superpowers` 设计/计划文档，不影响 Task 2 落地。

## Fix Task 2 Review Findings

changed files:
- backend/app/routers/dingtalk.py
- backend/tests/test_dingtalk_factory_brain_inbound.py

commit:
- `1e87e1ab` Keep DingTalk factory-brain routing aligned with intent flags

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py tests/test_dingtalk_factory_brain_inbound.py -q`
  - first output: `........FFFFFFFF..`
  - first failure summary: `8 failed, 10 passed in 5.62s`
  - cause: 新增工厂大脑路由测试把 orchestrator stub 掉后，旧的数据库落库断言不再成立，测试断言需要收紧到“是否走对路由”
  - final output: `18 passed in 4.31s`
- `cd backend && python -m compileall app/routers/dingtalk.py`
  - output: `Compiling 'app/routers/dingtalk.py'...`
- `git diff --check -- backend/app/routers/dingtalk.py backend/tests/test_dingtalk_factory_brain_inbound.py`
  - output: success

self-review:
- 根因是 `dingtalk.py::_should_route_factory_brain()` 还在使用旧 `task_type` 白名单，导致新 rule-first intent 虽然已经分类成功，钉钉入口仍不会进 `factory_brain`。
- 修复后改为直接信任 `intent.should_use_factory_brain`，同时继续保留空文本和 `/命令` 前缀走旧链路的兜底行为。
- 新增钉钉入站测试覆盖代表性业务问法：`产量`、`今天怎么样`、`库存够不够`、`合同余量`、`能耗是不是异常`、`成本核算发我`、`生成一张产量表格`、`昨日日报`，并补了一个明确非业务输入 `给我讲个轻松的笑话` 会回退旧链路。

concerns:
- 本轮只按 review 要求修了钉钉入站分流和最小测试覆盖，没有扩展 orchestrator 行为或改其他入口。

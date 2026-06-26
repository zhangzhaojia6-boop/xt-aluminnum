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

## Fix Task 2 Re-review Findings

changed files:
- backend/app/services/hermes_factory_brain_intent_service.py
- backend/tests/test_hermes_factory_brain_intent_service.py
- backend/tests/test_dingtalk_factory_brain_inbound.py

commits:
- `7dce82bf` Prevent factory brain from hijacking generic chat

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py tests/test_dingtalk_factory_brain_inbound.py -q` (red step after adding re-review tests)
  - output: `6 failed, 17 passed in 5.42s`
  - failed areas:
    - 普通非业务文本 `你好 / 随便聊两句 / 帮我随便说点什么` 仍被判成 `factory_brain`
    - `成品率 / 成材率 / 收得率` 仍被旧异常分支抢先命中
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py tests/test_dingtalk_factory_brain_inbound.py -q` (green step after fix)
  - output: `23 passed in 4.46s`
- `cd backend && python -m compileall app/services/hermes_factory_brain_intent_service.py`
  - output: success
- `git diff --check -- backend/app/services/hermes_factory_brain_intent_service.py backend/tests/test_hermes_factory_brain_intent_service.py backend/tests/test_dingtalk_factory_brain_inbound.py .superpowers/sdd/task-2-report.md`
  - output: success

self-review:
- 根因是 `classify_factory_brain_intent()` 的默认兜底仍把普通自然语言标成 `should_use_factory_brain=True`，所以 DingTalk 门禁虽然已经信任 intent flag，仍会把普通闲聊放进 `factory_brain`。
- 这次把默认 general fallback 改成 `should_use_factory_brain=False`，同时把 `你在干嘛` 一类普通聊天也收回到通用答复通道。
- 新增了三类确定性业务规则：`yield_analysis`、`feedback_learning`、`meta_skill_request`，并把 yield 规则前移，避免再次被 `是不是低了 / 是不是高了` 旧规则截走。
- DingTalk 新增入站测试不只测“笑话”，还覆盖了 `你好`、`随便聊两句`、`帮我随便说点什么` 这类最常见普通聊天兜底。

concerns:
- 未新增 yield / feedback / meta skill 的 DingTalk 正向入站测试，因为 DingTalk 入口当前只读取 `intent.should_use_factory_brain`；这次 focused tests 已证明新 intent 会被分类为业务通道，且普通聊天不会再进工厂大脑。

## Fix Task 2 Root Owner Review Findings

changed files:
- backend/app/services/hermes_factory_brain_intent_service.py
- backend/app/routers/dingtalk.py
- backend/tests/test_hermes_factory_brain_intent_service.py
- backend/tests/test_dingtalk_factory_brain_inbound.py

commits:
- `17fc7149` Restore root_owner gating for factory-brain-only DingTalk intents

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py tests/test_dingtalk_factory_brain_inbound.py -q` (red step after adding review tests)
  - output: `..........F.........F....`
  - failure summary: `2 failed, 23 passed in 4.91s`
  - failed cases:
    - `test_meta_skill_request_requires_root_owner`
    - `test_dingtalk_inbound_rejects_root_owner_only_factory_brain_request_for_non_root_owner`
- `cd backend && python -m pytest tests/test_hermes_factory_brain_intent_service.py tests/test_dingtalk_factory_brain_inbound.py -q` (green step after fix)
  - output: `25 passed in 5.00s`
- `cd backend && python -m compileall app/services/hermes_factory_brain_intent_service.py app/routers/dingtalk.py`
  - output: success
- `git diff --check -- backend/app/services/hermes_factory_brain_intent_service.py backend/app/routers/dingtalk.py backend/tests/test_hermes_factory_brain_intent_service.py backend/tests/test_dingtalk_factory_brain_inbound.py .superpowers/sdd/task-2-report.md`
  - output: success

self-review:
- 根因是 DingTalk 入口只看 `intent.should_use_factory_brain`，没有在进入 `run_factory_brain_turn()` 前再看 `intent.requires_root_owner`，所以 `meta_skill_request` 这类高权限意图会被普通管理员/经理绕过进工厂大脑。
- 这次直接复用现有 `classify_day1_actor()` 和 `require_root_owner_for_day1_report()`，让 factory_brain 也走同一套 `owner_required` 判断，没有新增第二套 root_owner 鉴权分支。
- `meta_skill_request` 现在会显式打上 `requires_root_owner=True`，并补了定向测试证明 flag 已生效、非 root_owner 的 DingTalk 请求会被 `403 owner_required` 拦住。

concerns:
- 本轮只补了 DingTalk factory_brain 的 root_owner 门禁和 `meta_skill_request` flag，没有扩展其他入口或改变 `run_factory_brain_turn()` 内部行为。

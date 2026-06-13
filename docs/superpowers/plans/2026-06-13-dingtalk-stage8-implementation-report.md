# 阶段八施工报告：RAG 知识库解释口径

## 目标

阶段八让 Agent 能回答“口径怎么定义、字段怎么用、异常怎么处理、权限怎么控制”这类规则问题。

重点不是让 AI 编实时数字，而是让它基于资料解释规则，并带上来源。

## 本阶段改动

- 扩展 `agent_knowledge_service` 的默认知识条目。
- 补充日报规则、MES 字段规则、车间规则、异常处理、填报补录、权限规则。
- 管理端概览增加知识口径总数和知识口径列表。
- 新增管理端只读接口：
  - `GET /api/v1/agent-management/knowledge`
  - `POST /api/v1/agent-management/knowledge/answer`
- 通讯治理台新增“知识口径”面板。

## 安全边界

- 知识库只解释规则，不查询实时生产数据。
- 遇到“今天、现在、实时、当前”等实时数值问题，会拒绝编造。
- 回答必须带来源；资料不足时返回“不能可靠回答”。
- 知识问答接口只面向管理员开放。
- 本阶段不改 MES、填报、日报生成、产量计算和能耗计算主链路。

## 验证结果

- `python -m pytest -q backend/tests/test_agent_knowledge_service.py backend/tests/test_agent_management_overview_service.py backend/tests/test_agent_management_router.py`
  - 结果：15 passed
- `node --test tests/agentManagementPage.test.js`
  - 结果：5 passed

## 五视角评分

- CEO 视角：9.8。减少口径反复解释成本，让管理层问规则时有标准答案。
- 工程师视角：9.8。只扩展独立知识服务和只读接口，没有侵入核心业务链路。
- 设计师视角：9.7。通讯治理台增加知识口径面板，信息清楚但不抢主流程。
- 安全视角：9.8。实时数值拦截、来源引用、管理员权限边界都保留。
- 真实用户视角：9.8。用户能快速知道“怎么算、从哪里来、为什么不能直接改”。

## 结论

阶段八已达到回归测试标准。当前版本能作为钉钉 Agent 和管理端解释口径的基础，但还没有开放普通员工自助问答入口。

# Parse 14 Review Analysis Action Matrix Design

## 背景

parse13 已经让 `analysis_handoff` 具备：

- `source_matrix`：人读的来源标签
- `source_variants`：机读的来源分类

现在后续 AI 已经能快速知道：

- 当前哪里有问题
- 为什么有问题
- 数据主要来自谁
- 数据属于哪类来源

但它还缺一层很实用的 deterministic 下一步提示：
面对不同 section 的状态与原因，AI 仍需要自己推断“先看什么动作”。

## parse14 目标

给 `analysis_handoff` 增加顶层 `action_matrix`，按 section 输出稳定的下一步动作键。

建议首批覆盖：

- `reporting`
- `delivery`
- `energy`
- `contracts`
- `risk`

## 设计原则

- 继续只做 deterministic contract
- `action_matrix` 只复用既有 `section_status / section_reasons / data_gaps`
- 不新增数据库查询
- 不输出自然语言建议

## 本阶段不做

- 不做 LLM 推理建议
- 不做动作优先级打分
- 不扩展前端页面

## 验收标准

- `analysis_handoff.action_matrix` 有 typed contract
- route tests 锁定 action matrix 字段
- build_factory_dashboard 定向测试锁定真实动作键
- focused 回归通过，若容器可用则补后端全量

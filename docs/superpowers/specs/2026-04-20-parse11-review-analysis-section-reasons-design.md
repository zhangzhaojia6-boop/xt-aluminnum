# Parse 11 Review Analysis Section Reasons Design

## 背景

parse10 已经让 `analysis_handoff` 具备顶层 `section_matrix`：

- 哪些 section 是 `healthy`
- 哪些 section 是 `warning`
- 哪些 section 是 `blocked`
- 哪些 section 是 `idle`

这让后续 AI 可以很快知道“哪里有问题”，但它仍然缺一层更细的 deterministic 解释：
为什么某个 section 进入了 `warning / blocked / idle`。

## parse11 目标

给 `analysis_handoff` 增加顶层 `section_reasons`，按 section 输出稳定的 reason keys。

建议首批覆盖：

- `reporting`
- `delivery`
- `energy`
- `contracts`
- `risk`

## 设计原则

- 继续只做 deterministic contract
- `section_reasons` 只复用既有 blocking reasons / attention flags / data_gaps / section status
- 不新增数据库查询
- 不生成自然语言说明

## 本阶段不做

- 不做优先级重算
- 不生成建议动作
- 不扩展前端页面

## 验收标准

- `analysis_handoff.section_reasons` 有 typed contract
- route tests 锁定 section reason fields
- build_factory_dashboard 定向测试锁定真实 reason keys
- focused 回归通过，若容器可用则补后端全量

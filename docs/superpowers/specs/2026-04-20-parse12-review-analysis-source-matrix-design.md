# Parse 12 Review Analysis Source Matrix Design

## 背景

parse11 已经让 `analysis_handoff` 能明确告诉后续 AI：

- 哪些 section 健康 / 告警 / 阻塞 / 空置
- 每个 section 为什么处于当前状态

但它仍然缺一个更快的来源入口：
如果 AI 想快速判断“这块数据主要来自谁”，现在仍要逐个 section 打开 `source_labels`。

## parse12 目标

给 `analysis_handoff` 增加顶层 `source_matrix`，按 section 输出稳定来源标签。

建议首批覆盖：

- `reporting`
- `delivery`
- `energy`
- `contracts`
- `risk`

## 设计原则

- 继续只做 deterministic contract
- `source_matrix` 只复用既有 section 的 `source_labels`
- 不新增数据库查询
- 不改写来源含义，不做推断

## 本阶段不做

- 不做来源权重排序
- 不做来源可信度评分
- 不扩展前端页面

## 验收标准

- `analysis_handoff.source_matrix` 有 typed contract
- route tests 锁定 source matrix 字段
- build_factory_dashboard 定向测试锁定真实来源集合
- focused 回归通过，若容器可用则补后端全量

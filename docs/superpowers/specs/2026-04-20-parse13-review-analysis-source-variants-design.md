# Parse 13 Review Analysis Source Variants Design

## 背景

parse12 已经让 `analysis_handoff` 具备顶层 `source_matrix`：

- 每个 section 主要来自谁
- AI 不需要下钻 section 内容就能先读懂来源格局

但它仍然缺一层更 machine-friendly 的来源分类：
当前 `source_matrix` 更偏人读标签，后续 AI 若要做规则路由或提示分流，仍需要把“主操直录 / 专项补录 / 系统汇总 / 结果发布”再映射成更稳定的来源变体。

## parse13 目标

给 `analysis_handoff` 增加顶层 `source_variants`，按 section 输出稳定的来源类别。

建议首批覆盖：

- `reporting`
- `delivery`
- `energy`
- `contracts`
- `risk`

## 设计原则

- 继续只做 deterministic contract
- `source_variants` 只复用当前 section 的既有来源语义
- 不新增数据库查询
- 不改写业务口径

## 本阶段不做

- 不做来源权重排序
- 不做可信度评分
- 不扩展前端页面

## 验收标准

- `analysis_handoff.source_variants` 有 typed contract
- route tests 锁定 source variants 字段
- build_factory_dashboard 定向测试锁定真实来源变体集合
- focused 回归通过，若容器可用则补后端全量

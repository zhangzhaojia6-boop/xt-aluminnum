# Parse 8 Review Analysis Freshness Design

## 背景

parse7 已经让 `analysis_handoff` 补齐了轻量趋势上下文：

- `current_output`
- `yesterday_output`
- `output_delta_vs_yesterday`
- `seven_day_average_output`

现在 AI agent 已经能读到：

- 当前状态
- 风险重点
- 基础趋势

但它仍然缺一层很关键的判断依据：这些数据到底“新不新”“稳不稳”“是否适合直接进入分析”。

## parse8 目标

parse8 的目标是给 `analysis_handoff` 再补一层 deterministic 的 freshness / confidence 上下文，例如：

- `sync_status`
- `sync_lag_seconds`
- `history_points`
- `published_report_at`
- `freshness_status`

## 设计原则

- 继续不做模型推理
- freshness 信息只复用现有 summary / sync contract
- 不新增数据库查询
- 不生成自然语言置信度结论

## 本阶段不做

- 不做概率评分模型
- 不接外部观测系统
- 不扩展前端页面

## 验收标准

- `analysis_handoff.freshness` 有 typed contract
- route tests 锁定 freshness 的关键字段
- freshness 字段只来源于既有 sync / history / publish 摘要
- focused 回归通过，若容器可用则补后端全量

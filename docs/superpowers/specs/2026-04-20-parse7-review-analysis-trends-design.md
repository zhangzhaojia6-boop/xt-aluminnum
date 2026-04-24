# Parse 7 Review Analysis Trends Design

## 背景

parse6 已经把 `analysis_handoff` 补成“可直接消费的信号包”：

- `readiness`
- `blocking_reasons`
- `priority`
- `attention_flags`
- `reporting / delivery / energy / contracts / risk`

这已经足够让 AI agent 先知道“当前状态”和“重点风险”。

但后续分析 agent 如果要回答“相较昨天怎么样”“当前值是否偏离近几天基线”，仍然需要自己再回头拆 `history_digest`。
这会让 AI 消费端继续重复做时间窗口聚合。

## parse7 目标

parse7 的目标是继续把 `analysis_handoff` 提升成“带比较上下文的输入包”，先补一个轻量 `trend` section：

- `current_output`
- `yesterday_output`
- `output_delta_vs_yesterday`
- `seven_day_average_output`

## 设计原则

- 继续只做 deterministic contract，不做预测推理
- 趋势上下文只消费现有 `history_digest`
- 不新增数据库查询
- 不生成自然语言趋势结论

## 本阶段不做

- 不做未来预测
- 不做时间序列模型
- 不扩展前端页面
- 不为每个 section 一次性加满所有趋势字段

## 验收标准

- `analysis_handoff.trend` 有 typed contract
- factory/workshop route tests 锁定趋势字段
- 趋势字段只来源于 `history_digest`
- focused 回归通过，若容器可用则补后端全量

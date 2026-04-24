# Parse 6 Review Analysis Signals Design

## 背景

parse5 已经为 `factory/workshop dashboard` 补齐了 `analysis_handoff`：

- `readiness`
- `blocking_reasons`
- `reporting / delivery / energy / contracts / risk`

这让后续 AI agent 已经有了一份稳定输入包。

但当前 handoff 仍然偏“原始主题分区”，还没有把真正需要优先关注的信号提炼出来。
这会导致后续分析 agent 继续自己从多个 section 里扫描重点，重复做规则判断。

## parse6 目标

parse6 的目标不是新增 AI 推理，而是先把 `analysis_handoff` 继续升级成“可直接消费的信号包”：

1. 增加顶层 `priority`
2. 增加顶层 `attention_flags`

让后续 AI agent 一拿到 handoff，就能先知道：

- 当前优先级高不高
- 当前最值得关注的是哪些 deterministic 信号

## 设计原则

- 继续只做 deterministic contract，不做模型推理
- `priority / attention_flags` 必须完全来自已有 typed summary contract
- 不新增新的数据库查询
- 不引入自然语言建议

## 建议规则

### priority

- `high`：存在 blocking_reasons
- `medium`：无 blocking，但有明显 warning 信号
- `low`：无 blocking，且无 warning 信号

### attention_flags

建议先覆盖这些稳定信号：

- `reporting_incomplete`
- `reporting_returned`
- `delivery_not_ready`
- `quality_blocker`
- `reconciliation_open`
- `energy_over_line`
- `contract_stalled`
- `exception_present`

## 本阶段不做

- 不生成行动建议
- 不输出自然语言分析
- 不引入模型调用
- 不改 dashboard 前端页面

## 验收标准

- `analysis_handoff.priority` 有稳定 typed contract
- `analysis_handoff.attention_flags` 有稳定 typed contract
- route tests 锁定 factory/workshop 的 deterministic 信号输出
- focused 回归通过，若容器可用则补后端全量

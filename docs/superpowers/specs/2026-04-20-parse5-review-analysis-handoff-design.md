# Parse 5 Review Analysis Handoff Design

## 背景

parse4 已把审阅端高频摘要 contract 基本收紧：

- `delivery_status`
- `energy_summary`
- `management_estimate`
- `contract_lane`
- `contract_progress`
- `blocker_summary`

这些块已经足够稳定，可以作为后续 AI 分析、预测、核算的输入边界。

但当前审阅接口仍然是“人看得懂的多块摘要”，还没有一个专门给 AI 消费的统一交接包。
这会导致后续分析 agent 继续自己拼字段、猜来源、重复做聚合。

## parse5 目标

parse5 的目标不是接入真实 AI 模型，而是先为审阅端补齐稳定的 `analysis_handoff` contract：

1. `factory_dashboard.analysis_handoff`
2. `workshop_dashboard.analysis_handoff`

它们要做到：

- 结构稳定
- 只含 AI 需要的关键输入
- 不依赖前端拼装
- 能直接作为后续分析 / 预测 / 核算 agent 的 deterministic 输入

## 设计原则

- 继续优先后端 contract，不先做前端炫技
- handoff 只做输入包，不做 AI 推理结果
- 不重复整份 dashboard payload，只提炼高价值块
- 每个 section 都要有明确来源和状态，避免 AI 消费时再猜

## 建议结构

### 1. 顶层元信息

- `target_date`
- `surface` (`factory` / `workshop`)
- `readiness`：当前数据是否足够支持 AI 分析
- `blocking_reasons`：若不够，明确哪些原因阻塞

### 2. 主题分区

建议至少拆成：

- `reporting`
- `delivery`
- `energy`
- `contracts`
- `risk`

每个分区只带：

- 当前核心数值
- 当前状态
- 关键摘要
- 上游来源提示

### 3. 结果约束

- handoff 不直接携带前端专用文案块
- handoff 不直接复制整个 `runtime_trace`
- handoff 中所有字段都来自已 typed 的 summary contract

## 本阶段不做

- 不接模型 API
- 不生成自然语言经营建议
- 不做预测算法
- 不做新的 dashboard 页面
- 不改已有填报链路

## 验收标准

- `factory_dashboard` 有 typed `analysis_handoff`
- `workshop_dashboard` 有 typed `analysis_handoff`
- route tests 锁定 handoff 的关键字段和 readiness 逻辑
- handoff 只依赖已稳定的 summary contract 构建，不直接读前端状态

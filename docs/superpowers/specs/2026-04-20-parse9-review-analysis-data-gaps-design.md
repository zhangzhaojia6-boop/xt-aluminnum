# Parse 9 Review Analysis Data Gaps Design

## 背景

parse8 已经让 `analysis_handoff` 具备：

- 当前状态与风险
- 优先级与关注信号
- 基础趋势
- 新鲜度 / 可信度上下文

后续 AI agent 已经能判断“当前是不是值得分析”。

但它仍然缺一层很实用的显式信息：哪些域是缺失的，哪些上下文虽然不阻塞但还不完整。
否则 AI 仍需要自己从各个 section 的 `idle / warming / stale` 状态再倒推“哪些东西不能直接下结论”。

## parse9 目标

给 `analysis_handoff` 增加顶层 `data_gaps`，明确列出当前仍存在的数据缺口或上下文缺失。

## 设计原则

- 继续只做 deterministic contract
- `data_gaps` 只复用已有 handoff section 与 freshness 规则
- 不新增数据库查询
- 不生成自然语言解释

## 建议首批 gap keys

- `report_unpublished`
- `history_unavailable`
- `sync_stale`
- `contracts_unavailable`
- `energy_unavailable`

## 验收标准

- `analysis_handoff.data_gaps` 有 typed contract
- factory/workshop route tests 锁定 gap keys
- focused 回归通过，若容器可用则补后端全量

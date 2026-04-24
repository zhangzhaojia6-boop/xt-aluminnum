# Parse 4 Review Summary Contracts Design

## 背景

parse3 已把两条主线收口：

- `inventory_keeper / utility_manager / contracts` 已完成一岗一表语义分离
- 审阅端 `来源泳道 / 结果卡映射 / 行级来源 / 上报状态提示` 已基本下沉到后端 contract

但管理员审阅端仍有一批关键摘要块没有完全 typed 化：

- `delivery_status`
- `energy_summary`
- `management_estimate`
- `blocker_summary`
- `contract_lane / contract_progress`
- 部分 `factory/workshop` 审阅摘要仍依赖 loose dict

这会让后续 AI 分析、预测、核算挂点继续建立在“能跑但结构偏松”的响应之上。

## parse4 目标

parse4 的目标不是新增业务，而是把审阅端剩余的关键摘要 contract 收紧，为下一段 AI 经营分析挂点提供稳定接口。

主目标分两部分：

1. `审阅摘要 contract typed 化`
2. `AI 分析挂点的响应边界预留`

## 设计原则

- 仍以管理员/管理层审阅面为主，不回头扩填报业务
- 优先后端 contract，再考虑前端展示
- 优先独立接口与高频摘要块，再处理边角返回体
- 不为未来 AI 逻辑硬编码实现，只先把挂点所需的数据边界变稳定

## 本阶段建议范围

### 1. 先收独立摘要接口

优先把这些接口变成明确 response model：

- `/api/v1/dashboard/delivery-status`
- `factory_dashboard.delivery_status`

理由：

- 它是管理端最直接的“交付是否就绪”口径
- 当前前端已有单独调用和 normalize 逻辑
- 先 typed 化最容易验证，也最容易卡住回归

### 2. 再收高频审阅摘要块

逐步补 schema：

- `energy_summary`
- `blocker_summary`
- `management_estimate`
- `contract_lane`
- `contract_progress`

优先级按“管理员是否直接看 / 后续 AI 是否会消费”排序。

### 3. AI 挂点边界

parse4 不实现完整分析 agent，只做准备：

- 审阅端关键摘要块字段名稳定
- 数值、状态、时间口径不再漂在 loose dict
- 后续 AI 分析只消费 typed contract，不直接读前端拼装结果

## 本轮不做

- 不做 MES 接入
- 不做成本核算逻辑实现
- 不做排产建议逻辑实现
- 不做新的前端大改版
- 不新增新的管理端页面

## 验收标准

- `delivery-status` 有明确 response model，且测试锁定
- `factory_dashboard` 里的交付摘要不再依赖 loose dict
- 至少一批高频审阅摘要块继续从 loose dict 收成 typed contract
- 后端全量通过，容器 healthy，`/readyz` 保持 `ready`

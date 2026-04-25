# 重构执行计划

当前阶段：第二轮前端收敛。

## 本轮目标

- 对齐目标图视觉方向：Apple 式克制高级感 + 工业生产中台。
- 修复 `KpiCard` 自动导入命名冲突。
- 深度增强 6 个既有页面：填报流程、工厂作业看板、日报交付、质量告警、成本估算、数据接入。
- 补齐 route contract e2e，防止三端边界回退。
- 同步文档中的 mock/fallback、按钮待接入和 legacy redirect 状态。

## 明确不做

- 不新增后端业务能力。
- 不新增数据库表。
- 不新增 MES 正式联调。
- 不新增大中心页面。
- 不移除 legacy redirect。
- 不把 AI 或 fallback 数据包装成真实生产结论。

## 验收命令

- `npm --prefix frontend run build`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 npm --prefix frontend run e2e`

本轮原则上不修改后端；若误改后端，必须补跑 `python -m pytest backend/tests -q`。

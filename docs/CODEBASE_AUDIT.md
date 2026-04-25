# 代码库审计记录

## 本轮发现

- `frontend/src/components/app/KpiCard.vue` 与 `frontend/src/components/cards/KpiCard.vue` 同名，触发 Vite 自动组件导入冲突。
- `frontend/src/views/review/RoadmapCenter.vue` 已从正式路由隔离并删除，但工作区仍有上一轮遗留的 staged/unstaged 混合状态。
- `frontend/src/reference-command/components/CommandPage.vue` 承载多个中心页，短期继续保留，避免本轮扩成多页面重写。
- 多个中心页仍使用 fallback/mock 数据，需要持续显式展示 `MockDataNotice` 或 source 标识。
- 成本中心定位为经营估算 / 策略口径，不是财务结算。
- 数据接入中心归属 `/admin/ingestion`，`/review/ingestion` 只做 legacy redirect。

## 本轮处理方向

- 将 app KPI 组件重命名为 `AppKpiCard`，消除自动导入冲突。
- 增强通用组件契约：状态、来源、表格 loading/empty、fallback 类型。
- 只深改 6 个指定页面，其余页面做轻量一致性检查。
- 新增 route contract e2e，锁定 `/entry`、`/review`、`/admin` 与 legacy redirect。

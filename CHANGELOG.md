# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses a 4-digit version scheme: `MAJOR.MINOR.PATCH.MICRO`.

## [0.4.3.3] - 2026-06-12

### Fixed
- 后端健康检查的活跃车间统计改为十二个生产车间口径，避免旧车间或辅助承载节点让管理端判断口径变成 18 个车间。
- 健康检查额外保留数据库启用节点数量，方便运维排查，但不再混入生产大屏主口径。

## [0.4.3.2] - 2026-06-12

### Changed
- 管理端继续对齐 Stitch + image2 工业蓝视觉，核心页面明确展示 MES 数据、人工填报和系统计算的来源分层。
- 管理端车间口径统一为十二个活跃车间，旧车间名称只作为别名归一化，不再进入核心概览。
- 系统设置页补齐十二车间、别名映射、机列台账、PC 工艺映射和数据源状态入口。

### Fixed
- 修复手机填报页“有填报问题”开关可能被底部操作区遮挡，导致现场人员点不开质量问题字段的问题。

## [0.4.3.1] - 2026-06-12

### Changed
- 完成 Stitch + image2 前端重构分阶段验收记录，明确管理端、手机填报端和核心指标页继续接入真实接口字段，不放假数字。
- 日报、能耗、手机扫码入口的展示口径更清楚，MES 数据、人工填报和算法结果继续分开呈现。

### Fixed
- 根目录后端测试门禁改为只收集真实后端测试目录，避免误扫临时缓存目录导致 Windows 权限失败。
- 手机端可选 MES 待补录请求失败时不再误触发退出登录，扫码填报主流程更稳。

## [0.4.3] - 2026-06-09

### Added
- 填报明细与车间看板新增 MES 对照异常视图，方便查看 MES 有工序但本地未填、批号未映射、重量不一致等问题。
- 新增缺报明细 Excel 导出，管理端和车间看板都可以按业务日期导出缺报核查表。
- 手机端扫码填报可带出 MES 中的规格、重量、上下机时间和料态字段，减少重复录入。

### Changed
- 扫码/MES 带出的字段全部保持可编辑，不再锁定，也不会因用户修正带出值而拒绝提交。

## [0.4.2] - 2026-06-04

### Changed
- 全厂昨日班次总览的全厂总产量口径改为成品库入库产量，班次与车间产量保留为过站下机参考。
- 管理端合同与库存导出改为带登录令牌的接口下载，避免浏览器新窗口导出时丢失登录状态。

### Fixed
- 修复本地端到端登录测试可能复用旧预览服务，导致误报登录不可用的问题。
- 修复云端工厂调度概览只存在每日在制料快照时仍回退到本地班次数据的问题。
- 修复后端测试在 `backend` 目录运行时读取项目路径不一致的问题。

## [0.4.1] - 2026-06-02

### Added
- 新增车间主任管理口径与“各车间看板”，支持机列填报、电工填报、外部 MES 明细、在制料和异常事务按车间聚合展示。
- 新增在线退火拆分口径：保留原在线退火二维码入口，同时新增新厂在线退火、园区在线退火的内勤与电工角色入口。

### Changed
- 车间主任登录管理端后仅进入并查看自己车间的看板，不能访问其他管理端页面。
- 冷轧产量口径区分开坯、中退、成品：开坯和中退只统计道次/过工序下机量，不计入车间总产量。
- 外部 MES 扩展数据、在制料、工艺记录按用户车间权限过滤后再进入管理端展示。

### Fixed
- 修复车间主任被登录页误判为“非管理员不能进入管理端”的问题。
- 修复已停用的虚拟角色二维码账号仍可能扫码换取 token 的安全问题。
- 修复在线退火拆分后能耗、产量映射仍混用旧车间的问题。

## [0.2.0.0] - 2026-05-25

### Added
- 管理端三大主视图骨架：`/manage/today`（系统总览）、`/manage/production`（生产）、`/manage/alerts`（异常与补录），统一中心编号 01/05/07
- 异常与补录单列时间线：`AlertsPage` 重写为 EventTimeline + DomainFilterChips + EventCard 组合，支持 4 域（生产/质检/对账/填报）筛选与 fallback 卡片
- `useAlertsTimeline` composable：基于 `Promise.allSettled` 的并行抓取 + 单端点失败兜底卡片 + inflight 令牌防竞态
- `KpiBar` 5 数组件、`WorkshopBarChart` 横向对比柱状图、`KeyEventList` 三槽要紧事、`CostLine` 单位换算（元 ↔ 万）
- `/manage/alerts/legacy` 路由保留旧三页面挂载入口

### Changed
- 旧入口（`overview` / `executive` / `entry-center` / `reconciliation` / `quality` / `anomaly` / `factory` / `workshop` 等）统一改为 `redirect`，通过 `preserveRouteState('/manage/alerts', { surface })` 保留 query/hash
- 模块目录与导航 catalog：质检模块入口统一为 `?domain=quality`
- `ManageShell` 头部、抽屉、品牌区颜色全部由 `--xt-*` token + `color-mix` 驱动，移除 hex/rgba 字面量
- `WorkshopBarChart` ECharts 系列颜色改用运行时 `readToken('--xt-color-accent')` 注入
- `KpiBar` / `CostLine` 数值列启用 `font-variant-numeric: tabular-nums`
- `TodayPage` / `ProductionPage` 顶部 720px 断点改为纵向堆叠
- `frontend/src/api/*.js` 14 个模块统一 `import { api } from './index.js'` 显式扩展名

### Fixed
- 设计 token 别名缺失：补全 `--xt-color-success/warning/danger/accent` 与 `--xt-text-on-accent`，消除组件未定义引用
- `useAlertsTimeline` / `useDashboardSnapshot` 并发抓取竞态：引入 inflight 令牌 + `try/finally` 保证 `loading.value` 释放
- `useAlertsTimeline.targetDate` 切换缺少 watcher：补 `watch(targetDate, () => load(), { flush: 'sync' })`
- `AlertsPage` 域比对用 `JSON.stringify` 受顺序影响：改为 `sameDomains(a, b)` 排序后比对
- `EventCard` 可达性：`<div role="button" tabindex="0">` 改为原生 `<button type="button">`
- `EventTimeline` 空态文案重复：仅在 empty 分支保留单条 `<p class="xt-event-timeline__empty">`
- `DomainFilterChips` 原生 `<button>` 上的冗余 `role="button"` 移除
- `KpiBar` 残留 `tone="neutral"` 分支删除（CSS 仅定义 positive/negative）
- `freshness` 状态映射：`fresh→green / stale→yellow / missing→red`，原始 green/yellow/red 透传
- e2e mocks 重复字段 `today_total_output` 删除，仅保留 `total_output_weight`

## [0.1.0.0] - 2026-05-09

### Added
- 落地前/后流程对比文档（`docs/落地前-旧流程`、`docs/落地后-新流程`、`docs/落地前后对比`，各含 HTML 与 PDF 版本）
- 首次引入 `VERSION`、`CHANGELOG.md`、`TODOS.md`，为后续发布节奏打基础

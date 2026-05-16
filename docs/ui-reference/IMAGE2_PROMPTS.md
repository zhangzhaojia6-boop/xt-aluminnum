# image-2 高保真 UI 提示词

> 用途：这些提示词用于快速生成 `鑫泰铝业 数据中枢` 的理想态高保真 UI 参考图。参考图只作为视觉、信息架构和组件还原基准，不作为静态截图嵌入产品。

## 统一生成规则

- 画布：桌面端 `1672 x 941`，移动端 `390 x 844`。
- 风格：深色工业科技风、蓝黑基底、冷蓝高光、低圆角、细边框、高信息密度但不拥挤。
- 气质：克制、成熟、企业级工业科技感，像真实生产协同平台，不像营销大屏。
- 组件：侧边导航、顶部操作栏、KPI、图表、表格、状态胶囊、审核队列、字段映射、AI 建议、移动表单必须统一。
- 数据：使用真实业务口径，不放离谱假数。产量以 `吨`，能耗以 `kWh`，天然气以 `m3`，成品率以 `%`，金额以 `万元` 或 `元/吨`，卷数以 `卷`。
- 文案：中文为主，产品名固定为 `鑫泰铝业 数据中枢`。`MES` 只作为外部生产系统或数据源出现。
- 避免：浅色通用后台、紫色渐变、夸张霓虹、巨型装饰英雄区、纯摆拍图表、英文假字、水印、模糊小字。

## 01 总览驾驶舱

```text
Create a high-fidelity desktop web app mockup for "鑫泰铝业 数据中枢" overview dashboard, 1672x941.
Subject: 系统总览主视图 showing production, delivery, quality, cost and AI evidence in one operational cockpit.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 224px left sidebar, 64px top header, main area 7:3, right evidence rail 360px, no floating marketing hero.
Data density: 6 KPI + 1 factory flow map + 3 charts + 1 pending binding table + 3 AI actions.
Component list: xt-layout/ManageShell, xt-layout/XtPageHeader, xt-data/XtKpi, xt-data/XtTable, xt-chart/XtFactoryMap, xt-chart/WorkshopOutputRanking, xt-chart/PendingAssignmentHeatmap, xt-chart/ReconciliationWaterfall, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, watermark, fake English placeholders.
Dark industrial command-center interface, restrained enterprise layout, cold blue accent, thin borders, 6px to 8px radius, precise data tables, no cheap sci-fi screen.
Main layout: fixed left sidebar with grouped modules, top bar with date selector and AI assistant button, dense main dashboard.
Hero area: factory status cockpit with daily output, monthly output, order fulfillment, yield rate, active machine lines, pending reviews, anomalies, delivered coils; every metric has unit labels.
Center panel: isometric aluminum factory flow map from casting to hot rolling, cold rolling, leveling, finishing, inventory and delivery, with live status badges and subtle blue data flow lines.
Right panel: AI operations commander with 3 concise recommendations, evidence source chips, freshness indicator, and pending actions.
Lower area: workshop output ranking, energy per ton trend, quality anomaly trend, pending fill-report binding table, all compact and readable.
Use realistic values such as daily output around 1800-2500 吨, never a six-figure daily output. Use Chinese labels only. No watermark.
```

## 02 登录与角色入口

```text
Create a high-fidelity login and role entry screen for "鑫泰铝业 数据中枢", 1672x941.
Subject: 登录与角色入口 with trusted account login, role shortcut chips and service readiness row.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: 5:4 split, left process preview 56%, right login card 44%, status row pinned inside login card bottom.
Data density: 1 login form + 4 role chips + 3 readiness badges + 1 factory process preview.
Component list: xt-data/XtLogo, xt-chart/XtFactoryMap, xt-data/XtStatus, xt-form/ElForm, xt-form/ElInput, xt-form/ElButton, xt-data/ParticleField.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, stock photo, cartoon illustration.
Dark industrial enterprise style, centered precise login card, left-side factory process preview, no marketing hero copy.
Show product mark, account/password login, role shortcut chips for 管理端, 审核端, 填报端, 班长端, and a small environment/status row with 外部生产系统连接, 数据库, 服务状态.
Use cold blue, graphite panels, slate text, thin borders, focused input states, professional Chinese typography.
No stock photos, no cartoon illustration, no muddy gradient background.
```

## 03 移动录入端首页

```text
Create a high-fidelity mobile app screen, 390x844, for shop-floor reporting home in "鑫泰铝业 数据中枢".
Subject: 独立填报端首页 for one-handed operator task entry and draft recovery.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: mobile single column, 128px identity header, 2x2 primary action grid, task list, bottom navigation 56px.
Data density: 4 primary actions + 4 KPI chips + 1 pending coil list + 1 last submission row.
Component list: xt-layout/EntryShell, xt-data/ReferenceKpiTile, xt-data/XtStatus, xt-form/EntryToolsPanel, xt-form/MobileSwipeWorkspace, xt-form/ElButton.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, management-only charts.
Target user is a machine operator scanning a machine-line QR code on the factory floor.
Layout: compact top identity area with role, workshop, machine line, shift and business date; primary actions for 扫码录入, 继续草稿, 今日已填, 异常补录.
Show machine-line binding, pending coils, draft count, last submitted time, offline retry status.
Large touch targets, clear hierarchy, no decorative text, no management-only content leak.
Industrial white background, blue actions, green success, amber pending, red anomaly, all labels in Chinese with units.
```

## 04 移动填报流程

```text
Create a high-fidelity mobile form screen, 390x844, for coil-level shop-floor reporting.
Subject: 填报流程页 with scanned coil identity, immutable locked fields and fast submit/draft actions.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: mobile single column, locked tracking card 112px, grouped form sections, bottom action bar 64px.
Data density: 5 locked fields + 6 form groups + 2 validation states + 3 bottom actions.
Component list: xt-layout/EntryShell, xt-form/EntryFieldInput, xt-form/XtFieldGroup, xt-form/ElInputNumber, xt-form/ElUpload, xt-data/XtStatus, xt-form/ElButton.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, dense manager dashboard.
Show scanned tracking card, locked fields for 卷号, 合金, 规格, 机列, 班次; locked fields should look immutable and trustworthy.
Form sections: 投料, 产出, 废料, 去向, 异常, 照片/备注. Use real units: kg, 吨, 卷.
Include submit button, save draft, scan again, validation state for locked field mismatch using clear operator-friendly Chinese.
The page must feel fast, practical, and one-handed. No dense manager charts on mobile.
```

## 05 生产与机列看板

```text
Create a desktop management page for factory machine-line board, 1672x941.
Subject: 工厂作业看板 showing machine-line cards, fill-report uploads and external production source clues side by side.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 224px sidebar, top filter bar, main area 7:3, left machine-line grid and binding table, right freshness and anomaly rail.
Data density: 5 KPI + 8 machine-line cards + 1 binding table + 3 charts + 1 freshness panel.
Component list: xt-layout/ManageShell, xt-layout/FactoryCommandShell, xt-data/XtKpi, xt-data/XtTable, xt-chart/WorkshopOutputRanking, xt-chart/PendingAssignmentHeatmap, xt-chart/ReconciliationWaterfall, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, fake realtime glow.
Layout: left navigation, top filters for business date, shift, workshop, data source; main area with machine-line cards and a live binding table.
Show external production system clues and fill-report uploads side by side: tracking card, workshop, machine line, shift, output weight, current destination, binding status.
Add charts: output by machine line, pending assignment heatmap, reconciliation waterfall between external source and fill terminal.
All numbers have units. Highlight real-time freshness and source labels. Professional dark industrial UI.
```

## 06 数据接入与字段映射

```text
Create a high-fidelity desktop data center page for "数据接入与字段映射中心", 1672x941.
Subject: 数据接入与字段映射中心 for source lanes, normalized fields, validation status and import history.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: 20:55:25 three-column layout with source lanes, mapping table, import batch drawer, history band at bottom.
Data density: 8 source lanes + 1 mapping table with 9 columns + 1 batch timeline + 1 validation summary.
Component list: xt-layout/ManageShell, xt-data/XtKpi, xt-data/XtTable, xt-data/XtStatus, xt-form/XtFilter, xt-form/ElUpload, xt-data/SourceBadge.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, automated-success claims.
Show source lanes: 外部生产系统, 填报端, Excel日报, 能耗表, 天然气表, 合同表, 成品率表, 图片/OCR候选.
Main table: source field, normalized field, unit, mapper status, validation status, last import, issue count.
Right panel: import batch timeline, row-level validation summary, freshness and rollback readiness.
Use precise tables, badges, filters and audit chips. Do not imply automated import for unconfirmed files.
```

## 07 审核端

```text
Create a desktop review workbench page, 1672x941, for production data review.
Subject: 审阅中心 for pending review, locked-field mismatch, owner gaps and evidence drawer.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: KPI strip, table-first main area 70%, right evidence drawer 30%, risk filter pinned to table header.
Data density: 4 KPI + 1 review table with 10 columns + 1 evidence drawer + 3 AI triage lines.
Component list: xt-layout/ManageShell, xt-data/ReferenceKpiTile, xt-data/ReferenceDataTable, xt-data/ReferenceStatusTag, xt-data/XtExecutionRail, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, automatic approval UI.
Show pending review queue, locked-field mismatch queue, missing owner field queue, and evidence drawer.
Each row includes source, workshop, machine line, tracking card, submitted by, submitted time, unit-bearing values, status and action.
Right side: AI triage suggestions with evidence links, but no automatic approval.
Visual style: white, industrial blue, compact, table-first, clear risk states.
```

## 08 报表中心

```text
Create a desktop report center page, 1672x941.
Subject: 日报与交付中心 for report generation, review, export, delivery checklist and blocked data items.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: 6 KPI strip, report list 60%, delivery checklist 40%, blocked items pinned at right top.
Data density: 6 KPI + 1 report table + 1 delivery checklist + 1 blocked item list + 1 trend chart.
Component list: xt-layout/ManageShell, xt-data/ReferenceDataTable, xt-data/ReferenceStatusTag, xt-data/XtKpi, xt-chart/ShiftOutputTrend, xt-form/XtFilter, xt-data/XtExport.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, fake delivered state.
Purpose: generate, review, export and deliver daily/monthly production reports.
Include daily output, monthly cumulative, yield rate, energy per ton, quality issue count, delivered coils, pending distribution.
Main panels: report generation status, report preview table, delivery checklist, blocked data items, export actions.
Show units everywhere and source/freshness chips for each section.
No fake success states; include mixed/fallback states where data source is not fully confirmed.
```

## 09 质量与异常

```text
Create a desktop quality and anomaly page, 1672x941.
Subject: 质量与告警中心 for anomaly map, quality issue table, severity and AI investigation summary.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 4 KPI strip, alert table 65%, AI triage/timeline rail 35%, anomaly map in second row.
Data density: 4 KPI + 1 alert table with 9 columns + 3 charts + 1 AI investigation panel.
Component list: xt-layout/ManageShell, xt-data/ReferenceDataTable, xt-data/ReferenceStatusTag, xt-data/XtKpi, xt-chart/ParetoChart, xt-chart/AnomalyTrend, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, alarm-wall decoration.
Show anomaly map by workshop and machine line, quality issue table, severity, impact tons, owner, due time, current handling state.
Charts: defect category Pareto, anomaly trend, unresolved aging.
Right panel: AI investigation summary, evidence, suggested next action.
Use red/amber/green sparingly, white enterprise UI, dense but readable.
```

## 10 成本与效益

```text
Create a desktop cost and benefit page, 1672x941.
Subject: 成本核算与效益中心 with operational estimate, caliber gaps, energy/cost trends and AI explanation.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: workshop tabs, 5 KPI strip, chart/table area 7:3, right caliber-gap and risk rail.
Data density: 5 KPI + 1 stacked cost chart + 1 energy per ton line + 1 workshop contribution table + 1 risk list.
Component list: xt-layout/ManageShell, xt-layout/FactoryCommandShell, xt-data/XtKpi, xt-chart/CostStackedBar, xt-chart/EnergyPerTonLine, xt-data/XtTable, xt-form/XtFilter, xt-data/XtAiActionCard.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, final-accounting language.
Show production, energy, gas, auxiliary material, loss and processing fee components by day/month/year.
Cards: 吨铝成本 元/吨, 加工费 万元, 能耗成本 万元, 辅材成本 万元, 毛利估算 万元.
Charts: cost composition stacked bar, energy per ton line, workshop contribution table, order profitability table.
Include clear source and calculation-caliber labels. Avoid financial-final language; it is operational estimate.
```

## 11 AI 助手

```text
Create a desktop AI control page for "鑫泰铝业 数据中枢" AI 助手, 1672x941.
Subject: AI 助手 with conversation, briefing inbox, watchlist, evidence chips and recommended operations actions.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 280px conversation list, 1fr chat work area, 360px briefing/watchlist rail, tool-call timeline above messages.
Data density: 1 conversation list + 1 active analysis thread + 5 evidence chips + 3 briefing cards + 6 watchlist topics.
Component list: xt-layout/ManageShell, xt-data/AiConversationList, xt-data/AiChatMessage, xt-data/AiBriefingInbox, xt-data/AiWatchlistPanel, xt-data/XtAiThinking, xt-data/XtAiActionCard.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, decorative chatbot mascot.
Use Chinese labels only. AI must show evidence source, freshness, confidence and approval requirement. Do not show automatic execution without review.
```

## 12 系统运维与可观测

```text
Create a desktop operations and observability page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 系统运维与可观测 showing healthz, readyz, service matrix, import jobs and event timeline.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: 4 KPI health strip, service matrix 60%, event timeline 40%, version and readyz fixed in page header.
Data density: 4 KPI + 1 service matrix with 8 rows + 1 event timeline + 2 trend mini charts + 1 failed-job list.
Component list: xt-layout/ManageShell, xt-data/XtKpi, xt-data/XtTable, xt-data/XtStatus, xt-chart/LatencyTrend, xt-chart/ErrorRateTrend, xt-form/XtFilter, xt-data/XtExecutionRail.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, fake all-green status.
Show backend, frontend, database, scheduler, import jobs, external source adapter, AI service, nginx/gateway health. Unknown probes must render as unknown, not success.
```

## 13 权限与治理中心

```text
Create a desktop permission and governance page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 权限与治理中心 showing role matrix, data boundary, audit log and risk accounts.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 4 KPI governance strip, role matrix 60%, audit log 40%, data boundary table in second row.
Data density: 4 KPI + 1 role matrix with 8 capability columns + 1 audit table + 1 risk account panel.
Component list: xt-layout/ManageShell, xt-data/XtKpi, xt-data/XtTable, xt-data/XtStatus, xt-form/XtFilter, xt-data/ReferenceStatusTag, xt-data/XtExecutionRail.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, hidden-permission shortcuts.
Use clear disabled states for admin, manager, reviewer, operator, owner-only, fill-only and team lead. Do not imply direct permission mutation without backend authorization.
```

## 14 主数据与模板中心

```text
Create a desktop master data and template center for "鑫泰铝业 数据中枢", 1672x941.
Subject: 主数据与模板中心 showing workshop master data, template config, enum config, alias mapping and field rules.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: configuration tabs, 4-column master data card grid, dense table, 360px right detail drawer.
Data density: 4 tabs + 8 master data cards + 1 table with 7 columns + 1 field-rule panel + 1 risk list.
Component list: xt-layout/ManageShell, xt-data/XtWorkshopGlyph, xt-data/ReferenceDataTable, xt-data/ReferenceStatusTag, xt-data/XtKpi, xt-form/XtFilter, xt-form/XtFieldGroup.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, direct-production mutation.
Keep actions realistic: view, filter, validate, preview, publish after review. Do not imply template publish without permission.
```

## 15 响应式录入体验

```text
Create a responsive entry experience reference for "鑫泰铝业 数据中枢", desktop canvas 1672x941 with a 390x844 mobile viewport preview.
Subject: 响应式录入体验 showing mobile fill workflow, draft/history recovery and desktop reviewer preview.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 390px mobile shell on left, 1fr reviewer preview on right, fixed 56px bottom navigation inside the phone shell.
Data density: 1 mobile task stack + 1 draft list + 1 history list + 1 reviewer preview + 3 validation states.
Component list: xt-layout/EntryShell, xt-form/MobileSwipeWorkspace, xt-form/EntryToolsPanel, xt-form/EntryFieldInput, xt-data/XtStatus, xt-form/ElButton.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, overlapping bottom action bars.
Show Chinese labels, large touch targets, no management-only confidential data inside the operator viewport.
```

## 16 库存与出入库中心

```text
Create a desktop inventory and movement page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 库存与出入库中心 showing coil destination from production to warehouse, transfer, cutting, customer delivery and pending state.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: flow table 65%, inventory structure and pending destination rail 35%, 420px coil detail drawer.
Data density: 5 KPI + 1 flow table with 9 columns + 3 inventory charts + 1 pending destination queue.
Component list: xt-layout/ManageShell, xt-layout/FactoryCommandShell, xt-data/XtKpi, xt-data/XtTable, xt-chart/InventoryAgingBuckets, xt-chart/OutboundTrend, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, fake inventory balance.
Dark industrial enterprise UI, all values with units, source and freshness chips visible.
```

## 17 合同与订单中心

```text
Create a desktop contract and order page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 合同与订单中心 showing contract list, order progress, production matching, delivery status and delayed risk.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: 5 KPI strip, contract table 60%, delivery calendar 40%, 420px production matching drawer.
Data density: 5 KPI + 1 contract table with 10 columns + 1 delivery calendar + 1 delayed risk list.
Component list: xt-layout/ManageShell, xt-data/XtKpi, xt-data/XtTable, xt-chart/DeliveryCalendar, xt-chart/FulfillmentTrend, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, fake customer data.
Use source import batch status from contract Excel dry-run. Show TODO endpoint boundary clearly if API is missing.
```

## 18 能源中心

```text
Create a desktop energy center page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 能源中心 showing electricity, gas, energy per ton, workshop comparison and missing energy inputs.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: 5 KPI strip, trend and stacked charts 7:3, right caliber and import batch rail.
Data density: 5 KPI + 1 energy per ton line + 1 workshop stack chart + 1 import batch table + 1 missing input list.
Component list: xt-layout/ManageShell, xt-data/XtKpi, xt-data/XtTable, xt-chart/EnergyPerTonLine, xt-chart/EnergyWorkshopStack, xt-form/XtFilter, xt-data/XtStatus.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, final accounting claims.
All values must show kWh, m3, 吨 and 元/吨 where applicable. Unknown source state must stay visible.
```

## 19 班长一屏

```text
Create a team lead operations screen for "鑫泰铝业 数据中枢", 1672x941.
Subject: 班长一屏 showing team progress, worker status, machine-line task confirmation and attendance exception confirmation.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: progress area 55%, worker and machine status 45%, fixed exception confirmation band at bottom.
Data density: 4 KPI + 1 worker table + 1 machine-line table + 1 exception band + 3 action buttons.
Component list: xt-layout/TeamLeadShell, xt-data/XtKpi, xt-data/XtTable, xt-data/XtStatus, xt-form/XtFilter, xt-form/ElButton.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, admin-only controls.
Use Chinese operator-facing labels. Confirmation actions require visible source and business date.
```

## 20 统计中心

```text
Create a desktop statistics center page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 统计中心 showing multi-dimensional production statistics, filters, trends and export boundary.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #ffffff.
Layout structure: 6 KPI strip, chart/table work area 70%, filter and caliber rail 30%, export in top-right.
Data density: 6 KPI + 3 charts + 1 statistics table + 1 caliber panel.
Component list: xt-layout/ManageShell, xt-data/XtKpi, xt-data/XtTable, xt-chart/ShiftOutputTrend, xt-chart/WorkshopScrapRate, xt-form/XtFilter, xt-data/XtExport.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, unexplained aggregate numbers.
Every metric must show unit, source and business date. Avoid giant decorative numbers without traceability.
```

## 21 文件导入中心

```text
Create a desktop file import center page for "鑫泰铝业 数据中枢", 1672x941.
Subject: 文件导入中心 showing dry-run upload, batch history, mapping preview and row-level validation failures.
Palette: #04101f, #020812, #5eb8ff, #4ecb8a, #f0b84a, #ff6b78, #c88f3c, #f7fbff.
Layout structure: upload area 30%, batch history table 70%, 420px mapping preview drawer.
Data density: 1 upload panel + 1 batch table with 8 columns + 1 mapping preview + 1 validation failure list.
Component list: xt-layout/ManageShell, xt-form/ElUpload, xt-data/XtTable, xt-data/XtStatus, xt-data/SourceBadge, xt-form/XtFilter.
Forbidden: purple-blue gradient, glassmorphism, SaaS three-card layout, emoji, papyrus, comic sans, silent production write.
Show dry-run/staging language, source chips and rollback readiness. Do not imply confirmed production import for unreviewed files.
```

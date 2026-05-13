# image-2 高保真 UI 提示词

> 用途：这些提示词用于快速生成 `鑫泰铝业 数据中枢` 的理想态高保真 UI 参考图。参考图只作为视觉、信息架构和组件还原基准，不作为静态截图嵌入产品。

## 统一生成规则

- 画布：桌面端 `1672 x 941`，移动端 `390 x 844`。
- 风格：冷白底、工业蓝、低圆角、细边框、高留白、高信息密度但不拥挤。
- 气质：Apple/OpenAI 式克制，企业级工业科技感，像真实生产协同平台，不像营销大屏。
- 组件：侧边导航、顶部操作栏、KPI、图表、表格、状态胶囊、审核队列、字段映射、AI 建议、移动表单必须统一。
- 数据：使用真实业务口径，不放离谱假数。产量以 `吨`，能耗以 `kWh`，天然气以 `m3`，成品率以 `%`，金额以 `万元` 或 `元/吨`，卷数以 `卷`。
- 文案：中文为主，产品名固定为 `鑫泰铝业 数据中枢`。`MES` 只作为外部生产系统或数据源出现。
- 避免：深色大屏、紫色渐变、夸张霓虹、巨型装饰英雄区、纯摆拍图表、英文假字、水印、模糊小字。

## 01 总览驾驶舱

```text
Create a high-fidelity desktop web app mockup for "鑫泰铝业 数据中枢" overview dashboard, 1672x941.
Cold white industrial interface, restrained Apple/OpenAI-like layout, industrial blue accent, thin borders, 6px to 8px radius, precise data tables, no dark sci-fi screen.
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
White industrial enterprise style, centered precise login card, left-side soft factory process preview, no marketing hero copy.
Show product mark, account/password login, role shortcut chips for 管理端, 审核端, 填报端, 班长端, and a small environment/status row with 外部生产系统连接, 数据库, 服务状态.
Use cold white, light blue, slate text, thin borders, focused input states, professional Chinese typography.
No stock photos, no cartoon illustration, no dark gradient background.
```

## 03 移动录入端首页

```text
Create a high-fidelity mobile app screen, 390x844, for shop-floor reporting home in "鑫泰铝业 数据中枢".
Target user is a machine operator scanning a machine-line QR code on the factory floor.
Layout: compact top identity area with role, workshop, machine line, shift and business date; primary actions for 扫码录入, 继续草稿, 今日已填, 异常补录.
Show machine-line binding, pending coils, draft count, last submitted time, offline retry status.
Large touch targets, clear hierarchy, no decorative text, no management-only content leak.
Industrial white background, blue actions, green success, amber pending, red anomaly, all labels in Chinese with units.
```

## 04 移动填报流程

```text
Create a high-fidelity mobile form screen, 390x844, for coil-level shop-floor reporting.
Show scanned tracking card, locked fields for 卷号, 合金, 规格, 机列, 班次; locked fields should look immutable and trustworthy.
Form sections: 投料, 产出, 废料, 去向, 异常, 照片/备注. Use real units: kg, 吨, 卷.
Include submit button, save draft, scan again, validation state for locked field mismatch using clear operator-friendly Chinese.
The page must feel fast, practical, and one-handed. No dense manager charts on mobile.
```

## 05 生产与机列看板

```text
Create a desktop management page for factory machine-line board, 1672x941.
Layout: left navigation, top filters for business date, shift, workshop, data source; main area with machine-line cards and a live binding table.
Show external production system clues and fill-report uploads side by side: tracking card, workshop, machine line, shift, output weight, current destination, binding status.
Add charts: output by machine line, pending assignment heatmap, reconciliation waterfall between external source and fill terminal.
All numbers have units. Highlight real-time freshness and source labels. Professional cold white industrial UI.
```

## 06 数据接入与字段映射

```text
Create a high-fidelity desktop data center page for "数据接入与字段映射中心", 1672x941.
Show source lanes: 外部生产系统, 填报端, Excel日报, 能耗表, 天然气表, 合同表, 成品率表, 图片/OCR候选.
Main table: source field, normalized field, unit, mapper status, validation status, last import, issue count.
Right panel: import batch timeline, row-level validation summary, freshness and rollback readiness.
Use precise tables, badges, filters and audit chips. Do not imply automated import for unconfirmed files.
```

## 07 审核端

```text
Create a desktop review workbench page, 1672x941, for production data review.
Show pending review queue, locked-field mismatch queue, missing owner field queue, and evidence drawer.
Each row includes source, workshop, machine line, tracking card, submitted by, submitted time, unit-bearing values, status and action.
Right side: AI triage suggestions with evidence links, but no automatic approval.
Visual style: white, industrial blue, compact, table-first, clear risk states.
```

## 08 报表中心

```text
Create a desktop report center page, 1672x941.
Purpose: generate, review, export and deliver daily/monthly production reports.
Include daily output, monthly cumulative, yield rate, energy per ton, quality issue count, delivered coils, pending distribution.
Main panels: report generation status, report preview table, delivery checklist, blocked data items, export actions.
Show units everywhere and source/freshness chips for each section.
No fake success states; include mixed/fallback states where data source is not fully confirmed.
```

## 09 质量与异常

```text
Create a desktop quality and anomaly page, 1672x941.
Show anomaly map by workshop and machine line, quality issue table, severity, impact tons, owner, due time, current handling state.
Charts: defect category Pareto, anomaly trend, unresolved aging.
Right panel: AI investigation summary, evidence, suggested next action.
Use red/amber/green sparingly, white enterprise UI, dense but readable.
```

## 10 成本与效益

```text
Create a desktop cost and benefit page, 1672x941.
Show production, energy, gas, auxiliary material, loss and processing fee components by day/month/year.
Cards: 吨铝成本 元/吨, 加工费 万元, 能耗成本 万元, 辅材成本 万元, 毛利估算 万元.
Charts: cost composition stacked bar, energy per ton line, workshop contribution table, order profitability table.
Include clear source and calculation-caliber labels. Avoid financial-final language; it is operational estimate.
```

## 11 库存与出入库

```text
Create a desktop inventory and movement page, 1672x941.
Show coil destination from production to warehouse, transfer, cutting, customer delivery and unfinished pending state.
Main view: flow table with tracking card, alloy, spec, weight, source workshop, destination, last handler, last time.
Charts: inventory by alloy/spec, aging buckets, outbound trend, pending destination queue.
White industrial enterprise UI, all values with units.
```

## 12 合同与订单

```text
Create a desktop contract and order page, 1672x941.
Show contract list, order progress, production matching, delivery status, customer, alloy/spec, required weight, produced weight, remaining weight.
Include fulfillment rate, delayed risk, delivery calendar, and source import batch status from real contract Excel reports.
Use high-density table and understated blue/green/amber status chips.
```

## 13 运维与告警

```text
Create a desktop operations and alerting page, 1672x941.
Show backend, frontend, database, scheduler, import jobs, external source adapter, AI service, nginx/gateway health.
Include readyz, healthz, last deployment, version, latency, error rate, failed jobs, rollback readiness.
Use white observability layout, precise status matrix, event timeline, no fake green status if source unknown.
```

## 14 权限与组织

```text
Create a desktop permission and organization page, 1672x941.
Show role matrix for admin, manager, reviewer, operator, owner-only, fill-only and team lead.
Show organization tree: workshop, team, machine line, shift, user binding, QR binding.
Include audit log table and risk accounts panel.
White enterprise UI, dense permission matrix, clear disabled states.
```

## 15 系统配置

```text
Create a desktop system configuration page, 1672x941.
Show master data, workshop templates, field rules, unit mappings, alias mappings, import templates and feature flags.
Main panels: configuration tabs, editable table preview, versioned publish history, validation issues.
Keep actions realistic: draft, validate, preview, publish after review. Do not imply direct production mutation without permission.
```

## 16 AI 分析与决策建议

```text
Create a desktop AI analysis workstation page, 1672x941.
Left: topic watchlist for production, energy, quality, cost, inventory, orders.
Center: conversational AI analysis with tool-call timeline, evidence chips, calculation references and confidence labels.
Right: recommended actions, affected workshops, data freshness, approval requirements.
The AI should feel like an operations analyst, not a decorative chatbot. White industrial interface, compact, high trust.
```

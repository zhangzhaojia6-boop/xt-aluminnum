# 云端前端数字与 MES SQL Server 核对报告

生成时间：2026-06-17  
云端前端：https://xtmijd.com  
系统名称：鑫泰铝业 数据中枢

## 一句话结论

核心 MES 包装产量可以对上。  
但“页面上每一个阿拉伯数字都必须和 MES SQL Server 原始表逐个相等”这个要求本身不成立，因为很多数字不是 MES 数据，比如日期、卷号、设备号、序号、用户数、后台配置、能耗、填报完整率、同步状态等。

## 本次实际做了什么

1. 用实际云端前端截图，覆盖 31 个路由页面。
2. 抓取这些页面实际请求的云端 API JSON，成功保存 47 个接口返回。
3. 直连 SQL Server 的 `XTAL` 数据库，读取 MES 相关表结构、行数、样本和关键汇总。
4. 按系统实际业务日口径核对核心包装产量：每天不是 00:00 到 24:00，而是 `07:30` 到次日 `07:30`。

证据目录：

- 截图总览：`artifacts/gstack-mes-audit-20260617/contact-sheet.png`
- 每页截图、文本、网络请求：`artifacts/gstack-mes-audit-20260617/`
- API 原始 JSON：`artifacts/gstack-mes-audit-20260617/api-json/`
- MES SQL Server 导出：`artifacts/gstack-mes-audit-20260617/mes-sqlserver/`
- 机器可读汇总：`artifacts/gstack-mes-audit-20260617/reconciliation-summary.json`

## SQL Server 表规模

| 表 | 行数 | 用途 |
|---|---:|---|
| `MES_Product` | 472537 | 产品/卷基础信息、在制状态 |
| `MES_ProductProcessRecord` | 692962 | 工序过程记录 |
| `WMS_InStockDetail` | 306451 | 包装/入库明细，本次包装产量核对用这张表 |
| `MES_Feeding` | 0 | 投料表，本次为空 |
| `WMS_Stock` | 308339 | 库存 |
| `MES_Device` | 50 | MES 设备 |

## 已确认能对上的核心数字

### 1. 2026-06-16 包装产量 `308.68`

页面/API 上看到的数字：

- `/manage/today`：`308.68`
- `/manage/production`：`308.68`
- `/api/v1/dashboard/daily-production?target_date=2026-06-16`：`daily_output = 308.68`，`packaging_output = 308.68`
- `/api/v1/aggregation/live?business_date=2026-06-16`：`packaging_output = 308.68`

SQL Server 核对公式：

```sql
SELECT SUM(NetWeight) / 1000
FROM WMS_InStockDetail
WHERE AllocationDate >= '2026-06-16 07:30:00'
  AND AllocationDate <  '2026-06-17 07:30:00';
```

SQL Server 结果：

| 业务日 | 行数 | NetWeight 合计 kg | 折算吨 |
|---|---:|---:|---:|
| 2026-06-16 07:30 到 2026-06-17 07:30 | 107 | 308680.0 | 308.68 |

结论：完全一致。

### 2. 2026-06-17 实时包装产量 `21.7`

页面/API 上看到的数字：

- `/manage/live`：`21.7`
- `/api/v1/aggregation/live?business_date=2026-06-17`：`packaging_output = 21.7`

SQL Server 核对公式：

```sql
SELECT SUM(NetWeight) / 1000
FROM WMS_InStockDetail
WHERE AllocationDate >= '2026-06-17 07:30:00'
  AND AllocationDate <  '2026-06-18 07:30:00';
```

SQL Server 结果：

| 业务日 | 行数 | NetWeight 合计 kg | 折算吨 |
|---|---:|---:|---:|
| 2026-06-17 07:30 到 2026-06-18 07:30 | 10 | 21702.0 | 21.702 |

结论：页面显示为 `21.7`，SQL Server 精确值为 `21.702`，属于显示四舍五入后对上。

## 容易误判的点

如果错误地按自然日 `00:00` 到 `24:00` 去算，会得出“不一致”的假结论。

| 日期口径 | SQL Server 结果 |
|---|---:|
| 2026-06-16 自然日 | 275.154 吨 |
| 2026-06-16 业务日 07:30 到次日 07:30 | 308.68 吨 |
| 2026-06-17 自然日 | 117.488 吨 |
| 2026-06-17 业务日 07:30 到次日 07:30 | 21.702 吨 |

所以核对这套系统时，必须使用业务日口径。

## 页面级判断

| 页面 | 截图状态 | 数字来源判断 |
|---|---|---|
| `/manage/live` | 已截图 | 混合来源。包装产量来自 MES 同步投影，已和 SQL Server 对上；填报进度、缺失数、同步状态不是 MES 原表数字 |
| `/manage/today` | 已截图 | 混合来源。`308.68` 包装产量已和 SQL Server 对上；能耗、班次、良率等来自本系统填报/计算 |
| `/manage/production` | 已截图 | 混合来源。包装产量已对上；在制、良率、工序产出等需要按对应字段再逐项建映射 |
| `/manage/workshop-dashboard` | 已截图 | 主要是车间视角汇总，包含本系统统计和部分 MES 投影 |
| `/manage/coils` | 已截图 | 卷列表。很多数字是卷号、批号、规格、车间编号，不是汇总指标；需要逐卷按 `BatchNumber` 等字段核对 |
| `/manage/fill-details` | 已截图 | 主要是本系统填报明细，不能直接要求每个数字等于 MES 原表 |
| `/manage/energy` | 已截图 | 能耗来自本系统移动端/班报，不是 MES SQL Server 原表 |
| `/manage/alerts` | 已截图 | 告警和异常统计，主要来自本系统规则与业务状态 |
| `/manage/attendance` | 已截图 | 考勤数据，不是 MES 原表 |
| `/manage/reports` | 已截图 | 报表页，取决于本系统报表数据 |
| `/manage/inventory` | 已截图 | 库存汇总页，需要按库存 API 和 `WMS_Stock` 另做字段级映射 |
| `/manage/contracts` | 已截图 | 合同页，很多数字是合同号、规格、数量、进度，不全是 MES 原表汇总 |
| `/manage/master` | 已截图 | 基础资料配置，不是 MES 原表生产数据 |
| `/manage/alias` | 已截图 | 别名配置，不是 MES 原表生产数据 |
| `/manage/mes-terminal-bindings` | 已截图 | MES 终端绑定配置，不是生产汇总 |
| `/manage/ai-assistant` | 已截图 | AI 会话/时间信息，不是 MES 原表生产数据 |
| `/manage/admin/settings` | 已截图 | 系统设置，不是 MES 原表生产数据 |
| `/manage/admin/users` | 已截图 | 用户管理，不是 MES 原表生产数据 |
| `/manage/admin/rules` | 已截图 | 规则配置，不是 MES 原表生产数据 |
| `/manage/admin/governance` | 已截图 | 治理配置，不是 MES 原表生产数据 |
| `/manage/admin/agents` | 已截图 | Agent 管理，不是 MES 原表生产数据 |
| `/manage/channels` | 已截图 | 渠道配置，不是 MES 原表生产数据 |
| `/manage/rag` | 已截图 | 知识库配置，不是 MES 原表生产数据 |
| `/manage/mapping-reconciliation` | 已截图 | 映射对账配置/状态，不是直接生产汇总 |
| `/manage/admin/qr-print` | 已截图 | 二维码/基础资料打印，数字多为编号和配置 |
| `/entry` | 已访问但跳转 | 当前管理账号会跳到 `/manage/admin/settings`，未看到真实录入页 |
| `/entry/fill` | 已访问但跳转 | 当前管理账号会跳到 `/manage/admin/settings`，未看到真实录入页 |
| `/entry/consumables` | 已访问但跳转 | 当前管理账号会跳到 `/manage/admin/settings`，未看到真实录入页 |
| `/entry/attendance` | 已访问但跳转 | 当前管理账号会跳到 `/manage/admin/settings`，未看到真实录入页 |
| `/entry/history` | 已访问但跳转 | 当前管理账号会跳到 `/manage/admin/settings`，未看到真实录入页 |
| `/entry/drafts` | 已访问但跳转 | 当前管理账号会跳到 `/manage/admin/settings`，未看到真实录入页 |

## 不能直接说“全部完全一致”的原因

通俗说，前端页面上的数字分成几类：

1. MES 原始生产数据：例如包装入库明细，可以用 SQL Server 表核对。
2. 本系统同步后的 MES 投影：先从 SQL Server 同步到本系统，再由页面读取。
3. 本系统人工填报数据：例如能耗、班次、部分产出、填报完整率。
4. 本系统配置数据：例如用户、设备、规则、二维码、别名。
5. 界面数字：例如日期、页码、序号、百分号、编号、卷号、规格。

只有第 1 类和第 2 类适合直接追到 SQL Server MES。第 3、4、5 类如果强行和 MES 原表比，一定会出现“看起来不一致”，但那不是数据错，而是来源本来不同。

## 当前结论

1. 核心包装产量已确认能与 SQL Server MES 按业务日口径对上。
2. 页面不是纯 MES 看板，而是“MES 同步数据 + 本系统填报数据 + 配置数据 + 界面状态”的混合系统。
3. 如果目标是“每个页面每个字段逐项审计”，下一步需要先做字段级清单：页面字段名、API 字段名、后端来源、SQL Server 表、SQL Server 字段、时间口径、单位换算。


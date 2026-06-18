# mes.xintaily.com 页面到 SQL Server 表底账

日期：2026-06-18

这份文档的目的很简单：把外部 MES 每个页面“看什么业务、主要从哪张表来、数据中枢该怎么接”说清楚。它不是凭页面名字猜数，而是按下面三类证据来归档：

1. SQL Server `XTAL.dbo.MES_Right` 菜单：确认有哪些页面，避免漏页面。
2. SQL Server 表结构：确认候选表是否真的存在。
3. MES MVC 页面：登录后抓页面表头、输入框、接口 URL，作为页面字段证据。

本次核心结论：

- 共同业务日：`07:30` 到次日 `07:30`，数据中枢和 MES 对齐时都按这个窗口解释日累计。
- MES 首页“当日投料量”：`MES_Product.FeedingWeight`，时间字段 `CreateDate`，过滤 `CurrentWorkShop` 非空。
- MES 首页“当日包装总量 66.1t”：`MES_ProductProcessRecord.EndWeight`，过滤 `Process=包装` 且 `WorkShop=精整`。
- 全厂包装不能只看精整，要看所有 `Process=包装` 的车间。
- 成品入库看 `WMS_InStock / WMS_InStockDetail`，不能拿包装工序产量当入库量。
- 6 月投料月累计差异必须通过对账接口暴露 `delta`，不能硬改成 MES 首页数字。

## 只读审计脚本

脚本位置：

```bash
python backend/scripts/audit_mes_page_table_mapping.py --json --output docs/audits/mes-page-table-audit-2026-06-18.json
```

需要的环境变量：

```powershell
$env:MES_MVC_BASE_URL='https://mes.xintaily.com'
$env:MES_MVC_USERNAME='<MES账号>'
$env:MES_MVC_PASSWORD='<MES密码>'
$env:MES_SQLSERVER_HOST='<SQL Server IP>'
$env:MES_SQLSERVER_PORT='1433'
$env:MES_SQLSERVER_DATABASE='XTAL'
$env:MES_SQLSERVER_USERNAME='<只读账号>'
$env:MES_SQLSERVER_PASSWORD='<只读密码>'
```

脚本只做 `SELECT`，只抓页面结构，不保存 cookie、token、密码或原始 HTML。

## MES 首页

| 首页指标 | 主表 | 核心字段 | 时间字段 | 过滤/口径 |
|---|---|---|---|---|
| 当日投料量 | `MES_Product` | `FeedingWeight` | `CreateDate` | 业务日窗口内，`CurrentWorkShop` 非空 |
| 首页包装总量 | `MES_ProductProcessRecord` | `EndWeight` | `EndDatetime` | `Process=包装`，MES 首页当前看到的是 `WorkShop=精整` |
| 全厂包装量 | `MES_ProductProcessRecord` | `EndWeight` | `EndDatetime` | `Process=包装`，包含精整、园区精整、拉矫车间等 |
| 成品入库量 | `WMS_InStock / WMS_InStockDetail` | `TotalNetWeight / NetWeight` | `InStockDate` | 入库事实，不和包装工序混用 |

全厂成品率主口径：

```text
全厂成品率 = 同一业务时间内 成品入库量 / 投料量 * 100
```

分母为 0 时返回 `null`，前端显示缺数，不显示假 0。

## 45 个 MES 菜单页面

说明：

- “已核实主表”表示表名已和 SQL Server 表结构或核心事实对上。
- “候选主表”表示页面控制器、页面接口、字段方向能指向这些表，但还应以脚本输出里的页面表头和接口结果继续复核。
- 同一个 URL 出现在两个菜单下时要保留两条，因为业务入口不同。

| # | 菜单路径 | URL | 业务含义 | 表映射 |
|---:|---|---|---|---|
| 1 | 销售管理 / 合同管理 | `/Contract/Index` | 销售合同 | 候选：`MES_Contract`, `MES_ContractDetail` |
| 2 | 销售管理 / 生产通知单查询 | `/ContractNotice/Index` | 生产通知单查询 | 候选：`MES_ContractNotice`, `MES_ContractNoticeDetail`, `MES_Contract` |
| 3 | 销售管理 / 发货通知单 | `/Delivery/Index` | 发货通知 | 候选：`MES_Delivery`, `MES_DeliveryDetail`, `WMS_OutStockDetail` |
| 4 | 销售管理 / 合同结构一览表 | `/Report/ContractStructReport` | 合同结构 | 候选：`MES_Contract`, `MES_ContractDetail`, `MES_ContractNotice`, `MES_Product` |
| 5 | 销售管理 / 客户管理 | `/Customer/Index` | 客户主数据 | 候选：`MES_Customer` |
| 6 | 销售管理 / 业务员管理 | `/Saler/Index` | 业务员主数据 | 候选：`MES_Saler` |
| 7 | 销售管理 / 乙方管理 | `/Company/Index` | 乙方公司 | 候选：`MES_Company` |
| 8 | 计划管理 / 生产通知单管理 | `/ContractNotice/Index` | 生产通知单管理 | 候选：`MES_ContractNotice`, `MES_ContractNoticeDetail`, `MES_Contract` |
| 9 | 计划管理 / 投料管理 | `/Feeding/Index` | 投料列表 | 已核实主表：`MES_Product`；核心字段 `FeedingWeight`, `CreateDate`, `CurrentWorkShop` |
| 10 | 计划管理 / 生产信息补录 | `/Production/Index` | 生产补录 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 11 | 计划管理 / 随行卡管理 | `/FollowCard/Index` | 随行卡 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 12 | 计划管理 / 三合一报表 | `/Report/ThreeReport` | 综合报表 | 候选：`MES_Product`, `MES_ProductProcessRecord`, `WMS_InStockDetail` |
| 13 | 计划管理 / 成品率报表 | `/Report/YieldReport` | MES 成品率报表 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 14 | 计划管理 / 铸轧车间看板 | `/Material/Board` | 铸轧/坯料看板 | 已核实主表：`MES_Material` |
| 15 | 计划管理 / 合同结构一览表 | `/Report/ContractStructReport` | 合同结构 | 候选：`MES_Contract`, `MES_ContractDetail`, `MES_ContractNotice`, `MES_Product` |
| 16 | 计划管理 / 工艺修改历史 | `/ProductHistory/Index` | 工艺修改历史 | 候选：`MES_ProductHistory`, `MES_Product` |
| 17 | 计划管理 / 生产通知单报表 | `/ContractNotice/Report` | 生产通知单报表 | 候选：`MES_ContractNotice`, `MES_ContractNoticeDetail`, `MES_Product` |
| 18 | 调度管理 / 生产车间实时查询 | `/Dispatch/Index` | 在制、当前车间/工序 | 已核实主表：`MES_Product`；候选工序表：`MES_ProductProcessRecord` |
| 19 | 调度管理 / 问题卷管理 | `/ProductProblem/Index` | 问题卷 | 候选：`MES_ProductProblem`, `MES_Product` |
| 20 | 调度管理 / 工艺延迟 | `/Dispatch/ProcessDelay` | 工艺延迟 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 21 | 质检管理 / 问题卷管理 | `/ProductProblem/Index` | 问题卷 | 候选：`MES_ProductProblem`, `MES_Product` |
| 22 | 质检管理 / 随行卡拍照 | `/FollowCard/Photo` | 随行卡图片 | 候选：`MES_Product`，图片接口另查 OSS/附件表 |
| 23 | 质检管理 / 成品率以及废料明细 | `/Inspection/YieldWasteReport` | 质检成品率/废料 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 24 | 质检管理 / 质量证明书 | `/Inspection/CertificateReport` | 质量证明书 | 候选：`MES_Product`, `MES_ProductProcessRecord`, 合同/客户表 |
| 25 | 车间生产管理 / 车间随行卡 | `/Workshop/Index` | 车间过站/随行卡 | 已核实主表：`MES_Product`, `MES_ProductProcessRecord` |
| 26 | 车间生产管理 / 成品率预警 | `/Report/YieldWarningReport` | 成品率预警 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 27 | 车间生产管理 / 车间报表 | `/Report/ProductionWorkshopReport` | 车间工序报表 | 已核实主表：`MES_ProductProcessRecord` |
| 28 | 退火管理 / 随行卡管理 | `/Anneal/IndexTake` | 退火随行卡 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 29 | 退火管理 / 退火录入 | `/Anneal/Index` | 退火录入 | 候选：`MES_Product`, `MES_ProductProcessRecord` |
| 30 | 退火管理 / 退火报表 | `/Anneal/AnnealReport` | 退火报表 | 候选：`MES_ProductProcessRecord` |
| 31 | 包装管理 / 包装录入 | `/Pack/Index` | 包装录入 | 已核实主表：`MES_ProductProcessRecord`；核心字段 `Process=包装`, `EndWeight`, `EndDatetime` |
| 32 | 包装管理 / 成品调拨单 | `/Allocation/Index` | 成品调拨 | 候选：`WMS_Stock`, `WMS_InStockDetail`, `WMS_OutStockDetail` |
| 33 | 坯料管理 / 坯料明细 | `/Material/Index` | 坯料明细 | 已核实主表：`MES_Material` |
| 34 | 坯料管理 / 机列生产管理 | `/Material/Board` | 机列生产 | 已核实主表：`MES_Material` |
| 35 | 公告管理 / 公告管理 | `/Notices/Index` | 公告 | 候选：`MES_Notices` |
| 36 | 成品库 / 库存查询 | `/Stock/Index` | 成品库存 | 已核实主表：`WMS_Stock`, `WMS_InStock`, `WMS_InStockDetail` |
| 37 | 系统管理 / 权限管理 | `/Right/Index` | 权限菜单 | 已核实主表：`MES_Right` |
| 38 | 系统管理 / 角色管理 | `/Role/Index` | 角色权限 | 已核实主表：`MES_Role`，关联 `MES_Right` |
| 39 | 系统管理 / 部门管理 | `/Department/Index` | 部门 | 候选：`MES_Department` |
| 40 | 系统管理 / 员工管理 | `/Member/Index` | 员工 | 候选：`MES_Member`, `MES_Department`, `MES_Role` |
| 41 | 系统管理 / 数据字典 | `/Dict/Index` | 字典 | 候选：`MES_Dict` |
| 42 | 系统管理 / 生产工艺管理 | `/Craft/Index` | 工艺 | 候选：`MES_Craft` |
| 43 | 系统管理 / 设备机器管理 | `/Device/Index` | 设备 | 已核实主表：`MES_Device` |
| 44 | 系统管理 / 登录日志 | `/Log/Index` | 登录日志 | 候选：`MES_Log` |
| 45 | 前世今生 / 前世今生 | `/Archives/Index` | 卷级追溯 | 候选：`MES_Product`, `MES_ProductProcessRecord`, `WMS_InStockDetail`, `WMS_Stock` |

## 数据中枢落地原则

1. 页面不直连外部 SQL Server。外部 MES 只读同步到本地 `mes_*` 投影表，前端只读后端 API。
2. 同名指标必须同含义：投料就是 `FeedingWeight`，包装就是工序 `EndWeight`，入库就是 WMS 入库。
3. `yield_matrix_lane` 保留为质检/历史参考，不再覆盖全厂主成品率。
4. 对不上 MES 首页的地方要通过对账接口暴露差异，不硬写死。

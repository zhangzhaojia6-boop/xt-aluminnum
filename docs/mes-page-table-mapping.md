# MES 页面到表映射底账

本文件记录 `数据中枢` 当前已核实的 MES 页面口径。前端只读后端 API；后端页面接口读取本地 `mes_*` 投影表，不在页面请求时直连外部 SQL Server。

完整页面清单见 [mes-xintaily-full-page-table-audit.md](./mes-xintaily-full-page-table-audit.md)，数据中枢页面对齐设计见 [mes-xtmijd-alignment-matrix.md](./mes-xtmijd-alignment-matrix.md)。只读审计脚本是 [audit_mes_page_table_mapping.py](../backend/scripts/audit_mes_page_table_mapping.py)。

| 页面/口径 | 外部来源 | 核心字段 | 时间字段 | 本地投影 | 当前用途 |
|---|---|---|---|---|---|
| MES 首页投料 | `MES_Product` | `FeedingWeight` | `CreateDate` | `mes_coil_snapshots.feeding_weight` + `source_payload.metadata.CreateDate` | 全厂投料主事实 |
| MES 投料管理 | `/Product/QueryListByFeeding` | `MES_Product` 字段 | `CreateDate` | `mes_coil_snapshots` | 投料页对账参考 |
| MES 包装统计 | `MES_ProductProcessRecord` | `EndWeight` | `EndDatetime` | `mes_workshop_process_records.output_weight_tons` | 全厂包装事实，过滤 `Process=包装` |
| MES 成品库/入库 | `WMS_InStock` / `WMS_InStockDetail` | `TotalNetWeight` / `NetWeight` | `InStockDate` / `CreateDate` | `mes_stock_records` | 成品入库事实 |
| 数据中枢本地投影 | 后台同步任务 | 清洗后的本地字段 | `business_date` | `mes_*` 表 | 前端和 API 的唯一读取层 |

全厂成品率主口径：

```text
全厂成品率 = 同一业务时间内 成品入库量 / 投料量 * 100
```

`yield_matrix_lane` 继续保留为质检/历史参考口径，不再覆盖全厂主成品率。

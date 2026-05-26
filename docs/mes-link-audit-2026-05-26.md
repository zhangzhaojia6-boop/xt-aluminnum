# MES 链路体检 + 读取场景盘点 — 2026-05-26

5/26 培训前对 MES 集成做的一次完整体检。结论：链路活的，5 个读取场景都在用。

## 1. 同步链路状态（prod 现场实测）

实测时间：2026-05-26 10:15 CST。

| 项 | 数值 | 说明 |
|---|---|---|
| `mes_sync_cursors.cursor_value` | 空字符串 | **设计如此**：MVC adapter 用 `updated_after` 时间窗拉，不依赖 server cursor token。空值不是 bug。 |
| `mes_sync_cursors.last_synced_at` | 10:14:30 +08 | 距实测 < 1 分钟 |
| `mes_coil_snapshots` 行数 | 669 | 覆盖 2050车间(204) / 新厂在线(118) / 园区在线(104) / 拉矫(31) / 精整剪切(43) 等 |
| `mes_machine_line_snapshots` 行数 | 50 | 机列字典在 |
| 最近 1 小时 run_log | 117 次 success，0 次 failed | 每分钟两路（adapter + projection），稳定 |
| 单次抓取量 | 50 条 / 60s | 命中 `MES_SYNC_LIMIT=50`，需要时调大 |

## 2. cursor_value 为空的根因

`mes_sync_service.sync_coil_snapshots` 调用 `adapter.list_coil_snapshots(cursor=cursor.cursor_value, updated_after=window_started_at, ...)`。MVC adapter（生产用的就是这个）实现里把 cursor 当 page token，但 MVC 端点不返回下一页 token，所以 `next_cursor` 永远是 `None`。窗口推进靠 `cursor.last_event_at`：每次拉取后更新成本批最新事件时间，下次窗口起点 = `last_event_at - MES_SYNC_WINDOW_MINUTES`（配置默认 10 分钟）。

**结论**：保持现状。空 cursor_value 是合约，不是漏洞。`last_event_at` 才是真正的进度位。

## 3. 读取场景盘点（5 处）

### 3.1 扫码查卷 — `scan_lookup_service.py`
- 入口：扫二维码 / 输入跟踪卡 / 输入物料号
- 查 `MesCoilSnapshot` 按 `qr_code` / `tracking_card_no` / `material_code` / `batch_no` / `coil_id`，按 `updated_from_mes_at desc` 取最新一条
- 同时查 `MesMachineLineSnapshot.has_table` 确认表存在，避免 fresh deploy 报错
- 返回卷的规格、合金、净重、当前/下道工序，给主操扫码看用

### 3.2 工厂指挥台 — `factory_command_service.py`
- 入口：管理端 `/factory-command` 实时大屏
- 查 `MesCoilSnapshot` 按 workshop / process 维度聚合，配 `CoilFlowEvent` 看流转
- 用 `current_workshop`、`workshop_code` 双口径匹配，`MesMachineLineSnapshot` 提供机列详情

### 3.3 实时态势 — `realtime_service.py`
- 入口：HUD 实时面板
- `_resolve_machine_binding_for_snapshot`：把 MES 机列代码反查到本地 `Equipment.id`，用 `resolve_mes_code` 经 `master_data` 别名表对齐
- 单条 coil 走 `_mes_snapshot_tracking_keys` 收集所有可能的跟踪 key 用于关联工单

### 3.4 移动端流转富化 — `mobile_report/flow_enrichment.py`
- 入口：主操扫码填报后，给汇总页加「这卷在 MES 里现在哪个工序」
- 内部调 `scan_lookup_service.flow_context_for_identifier`，捕 `ScanLookupUnavailable` 后返空字典——MES 端不可用时降级，不阻塞填报

### 3.5 合同进度投影 — `contract_progress_projection_service.py`
- 入口：管理端合同执行进度
- `db.query(MesCoilSnapshot).all()` 全量扫，配本地 `WorkOrder` / `WorkOrderEntry` 算合同每道工序完成率
- 数据量增长后需要按 `contract_no` 加索引或分页（已有 `ix_mes_coil_snapshots_contract_no`），目前 669 条全扫无压力

## 4. 培训当天可能的踩雷点

1. **MES 卷号在系统里没匹配到机列**：`resolve_mes_code` 走 `master_data` 别名表。今天 5/26 加的 15 个新机列还没在别名表里登记 MES code → MES 实际代码。**风险等级**：低，主操扫的二维码是工厂自己贴的 `XT-{ws}-{machine}-OP`，不依赖 MES code 对齐；MES 卷流转富化才用得到。
2. **MES 拉数延迟**：当前 1 分钟节奏，UI 上「卷的当前工序」最坏 60s 滞后。培训时不演示秒级实时即可。
3. **`current_workshop` 为空**：runtime 数据里 89 条 coil 该字段为空——是 MES 端历史数据，不是同步丢字段。

## 5. 行动项

- [x] 确认链路活，cursor 空是设计
- [x] 5 个读取场景都已盘点
- [ ] 培训后 1 周内：把 5/26 新增 15 机列在 `master_data_aliases` 里登记 MES 实际代码（前提：从 MES 端拿到这些机列的 code 对应表）

# MES API Sync Contract Phase 1

## 1. 目标

Phase 1 的目标不是让 `aluminum-bypass` 替代 `MES`。

本契约只保证一件事：

- `MES` 继续作为卷级流转唯一真源
- `aluminum-bypass` 通过 API 拉取卷级流转快照
- 再把这些快照同步到本地读模型，用于管理驾驶舱、经营估算和预警

## 2. 非目标

- 不改现场扫码流程
- 不要求双向写回 MES
- 不要求财务级真实利润
- 不要求卷级精确能耗归因

## 3. 接口范围

Phase 1 只要求两类读接口：

1. `tracking card info`
2. `coil snapshots`

另外，结合现场真实使用方式，Phase 1 还默认存在一个前端交互前提：

- 手机端扫码后，不是先人工填写所有头字段
- 而是先请求 `MES`
- 由 `MES` 返回这卷对应的头信息
- 这些头信息在统计/填报页中默认自动填充并锁定
- 一线人员只补充本工序实际操作数据

一句话：

> Phase 1 的一线录入页应该是 “MES 头字段自动带出 + 本工序操作字段人工补充”，不是“整页全手填”。

## 4. Tracking Card Info Contract

### Request

- Method: `GET`
- Path: `/tracking-cards/{card_no}`

### Response

```json
{
  "card_no": "RA260001",
  "process_route_code": "MES-RA",
  "alloy_grade": "A3003",
  "batch_no": "B20260411001",
  "qr_code": "QR-RA260001",
  "metadata": {
    "customer_name": "ACME"
  }
}
```

### Required fields

- `card_no`
- `process_route_code`

### Optional but strongly recommended clue fields

- `alloy_grade`
- `batch_no`
- `qr_code`
- `metadata`

### 面向手机扫码预填的推荐返回字段

如果 `MES` 当前能提供，建议优先返回这些字段。

它们可以：

- 直接作为正式字段返回
- 或先暂放在 `metadata`

推荐字段：

- `product_type`
- `status`
- `finished_spec`
- `production_schedule`

### 手机扫码后的页面行为约束

扫码成功后，页面应分成两类字段：

#### A. MES 自动带出并锁定

- `batch_no`
- `product_type`
- `alloy_grade`
- `status`
- `finished_spec`
- `production_schedule`

#### B. 现场人工补充

- `input_weight`
- `passes` / `道次`
- 机列主操填写的工艺数据
- 后台模板定义的自定义字段

这意味着：

- 页面不应允许一线随意改写 MES 返回的头信息
- 一线填写重点应落在“本工序新增事实”

## 5. Coil Snapshot Contract

### Request

- Method: `GET`
- Path: `/coil-snapshots`

### Query params

- `cursor`
- `updated_after`
- `limit`

### Response

```json
{
  "items": [
    {
      "coil_id": "coil-123",
      "tracking_card_no": "RA260001",
      "qr_code": "QR-RA260001",
      "batch_no": "B20260411001",
      "contract_no": "HT-2026-001",
      "workshop_code": "ZR2",
      "process_code": "casting",
      "machine_code": "ZD-1",
      "shift_code": "A",
      "status": "in_progress",
      "event_time": "2026-04-11T10:00:00+08:00",
      "updated_at": "2026-04-11T10:00:10+08:00",
      "metadata": {
        "next_process_code": "hot_roll"
      }
    }
  ],
  "next_cursor": "cursor-20260411100010"
}
```

### Required fields

- `coil_id`
- `tracking_card_no`

### Recommended fields

- `qr_code`
- `batch_no`
- `contract_no`
- `workshop_code`
- `process_code`
- `machine_code`
- `shift_code`
- `status`
- `event_time`
- `updated_at`

如 `coil snapshot` 能直接返回以下字段，也建议提供：

- `product_type`
- `finished_spec`
- `production_schedule`

若暂时不能独立成字段，也建议放在 `metadata` 中，方便 Phase 1 的手机扫码预填页先用起来。

## 6. 幂等与游标规则

- `coil_id` 是本地投影 upsert 的幂等主键
- 如果 `coil_id` 相同，则后到的更大 `updated_at` 覆盖更早快照
- API 允许时间窗重放，不应把重复数据视为错误
- `next_cursor` 可以为空，也可以与传入 cursor 相同

## 7. 失败与重试规则

- 单次拉取失败不能阻断本地系统已有读模型
- 同步服务需要记录：
  - `started_at`
  - `finished_at`
  - `status`
  - `fetched_count`
  - `upserted_count`
  - `replayed_count`
  - `lag_seconds`
  - `error_message`
- 重试由本地同步服务负责，契约层只要求 API 保持可重复读取

## 8. 限流与退避

- 客户端必须支持请求超时
- 客户端必须支持分页/批量拉取上限
- 客户端必须支持退避重试
- 建议服务端显式返回限流信息；若没有，也要保证客户端在 429/5xx 时退避

## 9. 管理层 SLA 对应关系

Phase 1 目标：

- 若某卷在 `2026-04-11 10:00` 于 MES 中更新
- 则 `aluminum-bypass` 管理驾驶舱应在 `2026-04-11 10:05` 前可见

因此本契约默认要求：

- 同步轮询粒度支持 `1 分钟`
- lag 可观测
- 投影更新时间可追踪

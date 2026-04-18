# 统计模块应用连接契约

## 1. 目标

这条连接面只服务一件事：

- 当生产日报进入发布链后，把“领导可读的统计摘要”以单次 HTTP `POST` 推给外部应用连接 API

它不是整站集成层，也不是插件市场。

## 2. 触发时机

- 触发源：`reporter_agent`
- 触发事件：日报已发布，且自动触达流程开始执行
- 非阻断原则：
  - 企业微信推送失败不能阻断日报生成
  - 应用连接推送失败也不能阻断企业微信推送
  - 失败只记录在 `report.report_data.app_connection_delivery`

## 3. 开关与配置

相关配置项：

- `APP_CONNECTION_ENABLED`
- `APP_CONNECTION_API_BASE`
- `APP_CONNECTION_API_KEY`
- `APP_CONNECTION_TIMEOUT_SECONDS`
- `APP_CONNECTION_PUSH_MODE`

模式约束：

- `disabled`：完全关闭
- `dry_run`：不发网络请求，只记录 payload 已生成
- `enabled`：真实发起 HTTP 请求

## 4. 请求契约

### 请求方法

- `POST`

### 请求头

```http
Authorization: Bearer <APP_CONNECTION_API_KEY>
Content-Type: application/json
```

### 请求体

```json
{
  "payload_version": 1,
  "dispatch_key": "report:123:2026-04-10T08:00:00+00:00",
  "report_date": "2026-04-10",
  "metrics": {
    "report_date": "2026-04-10",
    "total_output_weight": 123.4,
    "total_energy": 456.7,
    "energy_per_ton": 3.7,
    "reporting_rate": 100.0,
    "total_attendance": 86,
    "contract_weight": 98.7,
    "yield_rate": 96.5,
    "anomaly_total": 0,
    "anomaly_digest": "未发现关键异常",
    "in_process_weight": 45.2,
    "consumable_weight": 31.4
  },
  "leader_summary": "2026-04-10，今日产量 123.40 吨，异常 0 条。",
  "delivery_status": {
    "report_id": 123,
    "status": "published",
    "generated_scope": "auto_confirmed"
  },
  "summary_source": "deterministic"
}
```

## 5. 字段说明

- `payload_version`
  - 当前固定为 `1`
  - 下游必须按版本解析，避免未来字段漂移
- `dispatch_key`
  - 幂等键
  - 由 `report.id + published_at/generated_at/updated_at` 组成
- `report_date`
  - 业务日期
- `metrics`
  - 领导摘要使用的事实指标
  - 来源只能是现有 canonical/projection/report payload，不能新增推断事实
- `leader_summary`
  - 面向领导的文字摘要
- `delivery_status`
  - 当前日报在本系统内的交付状态
- `summary_source`
  - `deterministic` 或 `llm`

## 6. 成功与失败语义

- `2xx`
  - 视为发送成功
- 非 `2xx`
  - 视为发送失败
  - 当前不阻断主链，只做失败留痕
- 网络超时 / 连接异常
  - 视为发送失败
  - 当前不阻断主链，只做失败留痕

返回留痕写入：

- `status`: `disabled | dry_run | sent | failed`
- `push_mode`: `disabled | dry_run | enabled`
- `sent_at`
- `http_status`
- `detail`

## 7. Dry-run 语义

当 `APP_CONNECTION_PUSH_MODE=dry_run` 时：

- 不真正请求外部接口
- 仍然构建完整 payload
- 返回：

```json
{
  "status": "dry_run",
  "push_mode": "dry_run",
  "http_status": null,
  "detail": "payload_recorded_without_network"
}
```

这用于上线前联调，不允许把它当成“已真实送达”。

## 8. 下游接入要求

下游应用连接方至少要做到：

- 接收 `POST` JSON
- 校验 `Authorization: Bearer`
- 用 `dispatch_key` 做幂等去重
- 对 `payload_version` 做版本分支
- 把 `summary_source` 视为展示信息，不把它当业务事实来源

## 9. 当前边界

这份契约故意不包含：

- 多目标 fan-out
- 回调协议
- 重试队列协议
- 插件注册协议
- 泛化消息总线协议

本轮只保证“统计模块对外汇报接口”成立。

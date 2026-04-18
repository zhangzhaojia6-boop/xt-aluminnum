# 工作流事件契约

## 目标
- 为后续 webhook、钉钉、MES 或审批流接入提供统一输入。
- 保持现有 realtime/event bus 可继续使用，不在第一阶段直接发起外部出站请求。
- 让移动端“旧流程 -> 新流程”的迁移文案，和后端实际事件语义保持一致。

## 第一阶段边界
- 只定义统一事件包和现有事件发布点。
- 不新增 webhook 配置页。
- 不引入新的外部依赖、签名逻辑、重试队列或运维配置。
- 未来外接工作流时，统一由 publisher / adapter 层消费本契约，业务服务不得直接 `requests.post(...)`。

## 标准事件包

| 字段 | 含义 |
| --- | --- |
| `event_type` | 事件名 |
| `occurred_at` | 事件发生时间，ISO 8601 |
| `actor_role` | 触发角色 |
| `actor_id` | 触发人 ID |
| `scope_type` | 作用范围，当前阶段使用 `factory` / `workshop` / `team` / `machine` |
| `workshop_id` | 车间 ID |
| `team_id` | 班组 ID |
| `shift_id` | 班次 ID |
| `entity_type` | 业务实体类型 |
| `entity_id` | 业务实体 ID |
| `status` | 事件发生后的业务状态 |
| `payload` | 事件补充负载 |

## 第一阶段支持的标准事件

| 事件名 | 含义 | 当前状态 |
| --- | --- | --- |
| `entry_saved` | 随行卡条目保存为草稿 | 已接入 |
| `entry_submitted` | 随行卡条目正式提交 | 已接入 |
| `attendance_confirmed` | 班次考勤确认完成 | 已接入 |
| `report_reviewed` | 日报完成审核 | 已接入 |
| `report_published` | 日报完成发布 | 已接入 |

## 当前发布点
- `backend/app/services/work_order_service.py`
  - `entry_saved`
  - `entry_submitted`
- `backend/app/services/attendance_confirm_service.py`
  - `attendance_confirmed`
- `backend/app/services/production_service.py`
  - `attendance_confirmed`
- `backend/app/services/report_service.py`
  - `report_reviewed`
  - `report_published`

## 兼容策略
- realtime 流继续保留原业务字段，例如 `tracking_card_no`、`workshop_id`、`machine`。
- 标准事件包作为 `payload.workflow_event` 附加到 realtime 负载中。
- 这样既不打断现有页面消费，也让未来 publisher 有统一输入。

## 外接工作流建议
- 新增 `publisher` 适配层，而不是在业务服务中直连第三方。
- 适配层职责：
  - 读取 `workflow_event`
  - 选择目标渠道
  - 负责签名、重试、幂等和失败告警
- 适配层可兼容：
  - 钉钉机器人
  - MES 回调
  - 审批流 / BPM
  - 通用 webhook

## 前端文案约束
- 前端只表达“系统自动联动后续流程”。
- 第一阶段不提前承诺具体产品名，不出现“webhook”“签名”“重试”等技术词。
- 所有迁移文案只映射岗位与职责，不映射到个人姓名。

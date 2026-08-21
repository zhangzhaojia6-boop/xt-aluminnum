# 缺失事实精准通知与业务日隔离设计

## 目标

让 Hermes 把日报缺失事实只发给明确绑定的专项负责人或对应车间主任，打开补录页时不再出现可见的平滑滚动闪动，并保证钉钉证据不会跨业务日进入事实包候选；所有判断、回退和外发仍可沿 `AgentEvent -> AgentOutboxMessage -> ExternalMessageLog` 追溯。

## 已证实的现状

- 生产环境当前所有日报缺项都通过同一个 `dingtalk_work_notice` 通道发给管理员，一条消息混有多个岗位的补录任务。
- `users` / `employees` 中没有足够的车间主任和专项负责人钉钉绑定，不能靠现有角色字段直接精确投递。
- 钉钉企业通讯录可读取 77 个部门及成员、职务，但部分车间存在多个“主任”、只有“副主任”或无职务，不能用硬关键词静默猜测唯一责任人。
- `/entry/fill` 在内容渲染后对通知指定字段执行 `scrollIntoView({ behavior: 'smooth' })`，通知链接独有的平滑滚动会造成明显页面位移。
- `DailyFactBundle` 显式使用 `include_outside_business_context=True`，导致不属于目标业务日的钉钉证据进入多个日期的候选冲突。

## 设计原则

1. 不新建页面，不新建第二套组织表。
2. 复用 `CommunicationChannel.metadata_payload` 保存明确配置的组织责任关系。
3. 只有显式绑定才算精准路由；未绑定或冲突必须回退管理员并写 trace，不能按姓名、职位或关键词临时猜人。
4. 同一负责人只收到与自己有关的字段，不接收全厂混合清单。
5. 同一事项、同一业务日、同一目标不重复提醒；责任目标发生变化时允许向新增目标补发一次。
6. 跨日消息仍保留在 `MultimodalEvidence`，审计查询可用，但不进入目标日 `DailyFactBundle.conflicts`。

## 责任路由合同

真实工作通知通道继续使用 `channel_type=dingtalk_work_notice`。责任通道在 `metadata_payload` 中保存：

```json
{
  "daily_fact_notification": true,
  "daily_fact_admin_fallback": false,
  "recipient_name": "责任人姓名",
  "organization_path": "生产运行部/某车间",
  "responsibility": "车间主任或专项岗位",
  "daily_fact_fields": ["hot_roll_daily"],
  "daily_fact_owner_roles": ["energy_chief"]
}
```

匹配优先级：

1. `daily_fact_fields` 精确字段匹配。
2. `daily_fact_owner_roles` 精确责任角色匹配。
3. 没有匹配时走现有管理回退通道，并在事件 payload 记录 `routing_status=unresolved`。

管理员兜底通道必须显式配置 `daily_fact_admin_fallback=true`，且必须为已绑定、active、非 dry-run 的工作通知通道。专项负责人通道即使优先级更高，也不能接收未解析任务；找不到唯一兜底通道时只保留事件告警，不误发。

一条字段可以显式绑定多个负责人，例如两个在线退火车间主任；这是明确配置的多收件人，不是冲突。配置程序只写显式选择结果，不根据模糊职位自动决定。

## 外发与审计

- 每个责任通道分别创建 outbox，内容只包含该通道匹配的 assignments。
- outbox payload 保存 `recipient_name`、`organization_path`、`routing_status`、`assignments`。
- 事件 payload 保存本轮 `notification_target_keys`、`action_notification_outbox_ids` 和 `routing_status`，只作为审计快照，不参与第二套状态机控制。
- 每个通道用“业务日 + 通知状态 + 该通道 assignment 签名”生成 dedupe key。现有 outbox 已按 agent、channel 和 dedupe key 去重，因此新增负责人会自然收到一次，旧目标字段不变时自然复用旧 outbox。
- 无责任映射时管理员收到兜底通知，同时 `/manage/alerts` 可看到未解析责任关系。

## 补录页首帧

通知链接仍保留 `business_date`、`entry_fields`、`owner_role` 和 `trace_id`。字段节点渲染后的定位改为同步 `auto` 滚动，并继续 `preventScroll` 聚焦；Vue 的 `nextTick` 发生在浏览器绘制前，因此不会显示一段平滑移动过程。

## 业务日隔离

`DailyFactBundle` 使用 `query_dingtalk_evidence` 的默认业务日过滤。显式日期不匹配、由事件/创建时间推断到其他业务日、或无法安全归属的消息均不进入该日期事实包。没有正文日期但钉钉事件时间能唯一落入一个生产业务窗口的消息仍可属于该窗口，避免把识别规则做死；它不得再次进入相邻业务日。原始证据和 trace 不删除；需要全量审计时仍可显式使用 `include_outside_business_context=True`。

## 验收标准

- 两个相邻业务日构建事实包时，同一条无正文日期证据可按可靠事件时间属于其中一个业务日，但不得在另一日再次产生 candidate conflict；完全无法安全归属时两日均不采用。
- 全量审计查询仍能按 evidence id 找到被隔离消息。
- 一个专项负责人通道只收到其 owner role 的字段。
- 一个车间主任通道只收到显式配置给该通道的日报字段。
- 未配置字段回退管理员并带 `routing_status=unresolved`。
- 相同通道和字段子集重复同步不新增 outbox；新增责任通道后该通道自然产生一条新 outbox，旧通道不重复。
- 补录页面源码和浏览器行为均无 smooth scroll，指定字段仍自动定位并获得焦点。

## 回滚

- 代码回滚后恢复单通道通知和旧事实包读取行为。
- 责任通道只是现有表中的普通行，可停用而无需删表。
- 不修改原始 `MultimodalEvidence`、历史 `AgentEvent`、outbox 或外部日志。

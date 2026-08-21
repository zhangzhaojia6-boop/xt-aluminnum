# 缺失事实精准通知与业务日隔离生产验收

日期：2026-08-21

## 结论

本轮闭环通过。缺失事实工作通知已按显式责任配置拆分，车间主任进入本车间管理看板，专项负责人进入既有补录页；通知目标变化时会生成新的目标级去重签名，不会复用错误收件人的旧消息。跨业务日钉钉证据不再进入相邻日报事实包，原始证据和 trace 仍保留。

## 版本与门禁

- 功能验收版本：`5121dea1abdba69d694e0a165b1f9cb7e9b38934`
- Hermes 可信版本：`4d4452067cb43ebcd437eba78b0c67d9f1c64652`
- CI：run `32450852682`，backend-tests、frontend-build、compose-smoke 全部成功。
- 精确生产部署：run `32451424966` 成功。
- 生产部署后 `versionz` 返回上述 Data Hub 与 Hermes SHA。
- 三个生产服务均为 `active`；`readyz.status=ready`。
- `readyz` 中 database、pipeline、schedule、uploads、equipment_binding、mes_sync 均为 `ok`；MES 最近同步成功且为 `fresh`。`iot_energy_sync=unconfigured` 是尚未接入物联网能耗源，不作为本轮故障。
- 127 字段日报合同门禁通过，最大允许误差仍为 `20.0`，未缩小字段分母。

## 实现证据

### 通知路由

- 生产显式配置 5 名专项负责人、6 名车间主任和 1 个管理员兜底通道。
- 车间主任通道使用 `daily_fact_recipient_mode=supervisor`，通知进入 `/manage/workshop-dashboard`，不再把无补录权限的主任送到 `/entry/fill`。
- 专项负责人通道使用 `daily_fact_recipient_mode=specialist`，继续进入 `/entry/fill` 并只携带本人负责字段。
- 有歧义或没有明确人员的岗位没有猜人，51 个未解析字段在当时生产预演中进入管理员兜底并保留 `/manage/alerts` trace。
- 去重签名包含收件模式和实际目标路由，责任配置从专项负责人切换为主任时不会复用旧入口消息。
- 生产组织配置备份：`/srv/aluminum-bypass/backups/daily-fact-routing-20260821T043657Z.json` 与 `/srv/aluminum-bypass/backups/daily-fact-recipient-mode-20260821T051840Z.json`，权限均为 600。

### 跨业务日隔离

- `2026-08-19` 事实包采用证据 ID：`700, 712, 716`。
- `2026-08-20` 事实包采用证据 ID：`725, 730`。
- 两日采用证据交集为空。
- 使用 `include_outside_business_context=True` 的审计查询仍可在两日查询中找到被隔离证据，原始证据未删除，审计总数为 739。

### 页面与真实浏览器

- `/entry/fill` 的指定字段滚动使用 `behavior: auto`，焦点继续使用 `preventScroll: true`；生产真实浏览器验证无可见平滑滚动、无页面错误、无控制台错误。
- 真实车间主任扫码身份打开 `/manage/workshop-dashboard?business_date=2026-08-20&trace_id=acceptance-supervisor-date-fix`。
- 页面保持在车间看板，保留 `business_date=2026-08-20` 和 `trace_id`，首屏显示 `8月20日 日报`。
- 该页面发出的 7 个带业务日期接口请求全部使用 `2026-08-20`，没有先请求 8 月 21 日再切换。
- 页面显示“链路在线”，page error 与 console error 均为 0。
- 浏览器截图保存在本机临时目录 `C:\Users\xt\AppData\Local\Temp\workshop-dashboard-date-acceptance.png`，未写入仓库。

## 测试证据

- 定向前端测试：`manageFillDetailsAudit.test.js`、`businessDateDefaults.test.js`、`routerGuardRules.test.js`，52/52 通过。
- 前端生产构建通过。
- CI 后端全量测试通过。
- CI 生产 Compose 配置、健康检查、登录及 Playwright smoke 通过，Playwright 为 1/1。
- 两轮代码审查均为 `APPROVE`，最后一轮未发现日期循环、重复加载、越权或跨日风险。

## 真实外发边界

本轮没有为了验收额外打扰真实责任人。用户此前明确要求先跳过真实责任人发送，且已经自行模拟责任人发送；因此保留现有真实通道和审计能力，但未另造两条“测试通知”。这项记录为有意跳过，不描述为真实外发通过。

## 回滚

- 代码可回滚到 `0238d0ad0c0a2c8c4c4070e11ffb6bac80c94e49`。
- 责任通道可停用，不需要删表；生产配置可用上述两个备份恢复。
- 回滚不删除 `MultimodalEvidence`、`AgentEvent`、`AgentOutboxMessage` 或 `ExternalMessageLog`，审计 trace 保留。

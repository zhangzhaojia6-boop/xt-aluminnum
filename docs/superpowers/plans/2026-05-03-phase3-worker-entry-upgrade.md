# Phase 3 · 工人入口升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把工人入口从"网页输账号密码"升级到"钉钉里点一下 → 扫码 → 提交"。不依赖 MES API 联调；本地 `mes_coil_snapshots` 表作为卷信息登记源（由手填 / 导入 / 后续 MES 同步任意一种填充均可）。

**Architecture:** 钉钉 H5 免登录走 `dingtalk_service` 的 OAuth → 签名 → `JSAPI` → 绑定 `User.dingtalk_user_id`，绕过用户名/密码；`routers/dingtalk.py` 补 `/api/v1/dingtalk/h5-login` 端点换 token；`MobileEntry.vue` 在钉钉容器内自动走免登录，非钉钉环境仍允许账号登录作为兜底。扫码即填：扫到的 QR（由 MES 产生或本地 `master/QRCodePrint.vue` 打印）进 `mobile/scan-lookup` 端点，按 `MesCoilSnapshot.qr_code` → `MesCoilSnapshot.tracking_card_no` → `Equipment.qr_code` 的顺序命中，把卷头字段或机台身份带出并锁定，现场仅补充本工序事实。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Element Plus Plus (es/mobile), 钉钉 JSAPI, node:test

---

## Scope

In scope:

- `dingtalk_service.py` 的 `resolve_mobile_identity` 从 placeholder 升级为真实 OAuth 换 userid。
- 新端点 `POST /api/v1/dingtalk/h5-login`，入参 `{ code }`，出参 `{ access_token, user }`（复用现有 JWT）。
- `MobileEntry.vue` 在检测到 `window.dd` 或 UA 含 DingTalk 时自动走免登录；失败回落到账号登录。
- 钉钉工作通知通道打通：`dingtalk_service.send_work_notification(userid, content)` 真实调用 `topapi/message/corpconversation/asyncsend_v2`；供 Phase 2 的 reporter/reminder agent 使用。
- `admin/users` 侧允许"从钉钉通讯录拉成员"一键建账户（匹配 `unionid` / `mobile`）。
- 新端点 `GET /api/v1/mobile/scan-lookup?qr=...`：按 `MesCoilSnapshot.qr_code` → `MesCoilSnapshot.tracking_card_no` → `Equipment.qr_code` 顺序命中；返回 `{ source, header_fields, lock_keys }`。
- `CoilEntryWorkbench.vue` 接入 scan-lookup，扫码后头字段只读锁定，仅显示需现场补充字段（本工序新增事实）。
- `master/QRCodePrint.vue` 打印的机台 QR（Equipment.qr_code）也能走同一 scan-lookup 流程。

Out of scope:

- 不做钉钉 E-HR / 考勤打卡集成。
- 不做 MES 接口联调（无 MES 也要能跑）。
- 不引入新的卷级业务模型；仅复用现有 `MesCoilSnapshot`（卷级）与 `Equipment.qr_code`（机台）。
- 不做离线缓冲（留给后续）。
- 不改已有的 `MobileShiftReport` schema。

---

## Task 1: 钉钉 H5 免登录闭环

**Files:**

- Modify: `backend/app/services/dingtalk_service.py`
- Modify: `backend/app/routers/dingtalk.py`
- Modify: `backend/app/config.py`（确认 `DINGTALK_CORP_ID / APP_KEY / APP_SECRET / AGENT_ID` 可被 .env 覆盖）
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/Login.vue`（钉钉容器自动跳转）
- New: `frontend/src/api/dingtalk.js`
- New: `frontend/public/dingtalk-jsapi-loader.js`（按钉钉文档推荐的动态加载）
- Test: `backend/tests/test_dingtalk_h5_login.py`
- Test: `backend/tests/test_dingtalk_service.py`
- Test: `frontend/tests/dingtalkAutoLogin.test.js`
- Test: `frontend/e2e/mobile-dingtalk-login.spec.js`

- [ ] **Step 1: 写失败测试**

- `POST /api/v1/dingtalk/h5-login` body `{code: 'abc'}`：
  - 配置缺失（corp_id 为空）→ 400 `dingtalk_not_configured`。
  - 配置齐备但 code 无效 → 401 `dingtalk_code_invalid`。
  - code 有效但无本地 User 绑定 → 404 `dingtalk_user_not_bound` 且响应体带 `dingtalk_user_id`（供 admin 绑定）。
  - 成功 → 返回 `{access_token, user:{id, role, ...}}`，与账号登录同构。
- `dingtalk_service.exchange_code(code)` 必须走 mock 的 HTTP 客户端（不实跑网络）。
- 前端：`window.dd` 存在 + 有 corp_id 时，`MobileEntry.vue` mount 阶段先尝试 `dd.config` + `dd.getAuthCode` → `/h5-login`；失败回落到账号登录并提示"钉钉鉴权失败，改用账号登录"。
- 非钉钉 UA：直接显示账号登录表单，不尝试 JSAPI。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_service.py -q
npm --prefix frontend test -- frontend/tests/dingtalkAutoLogin.test.js
```

- [ ] **Step 3: 实现 OAuth 换 token**

在 `dingtalk_service.py` 新增：

- `async def fetch_access_token() -> str`：调 `gettoken.json`，带 in-process cache（7200s 提前 300s 刷新）。
- `async def exchange_code(code: str) -> dict`：调 `topapi/v2/user/getuserinfo`（新版）拿 `unionid` 和 `userid`。
- `def issue_jwt_for_dingtalk_user(db, dingtalk_user_id) -> tuple[User, str]`：按 `User.dingtalk_user_id` 找 User → 调既有 `app.core.auth.create_access_token({'sub': user.username, ...})`。

`routers/dingtalk.py` 新增 `/h5-login` 路由编排上述三步。

- [ ] **Step 4: 前端免登录**

- `dingtalk-jsapi-loader.js`：按钉钉文档动态加载 `dingtalk.open-platform/jsapi/2.10.3/...`。
- `frontend/src/api/dingtalk.js`：`dingtalkH5Login(code)`。
- `Login.vue` 在 `mounted` 检测 `navigator.userAgent.includes('DingTalk')`，有则 dispatch 到 `MobileEntry.vue` 或直接触发 JSAPI 流程。
- 成功后把 token 写入既有 auth store，进入 `/mobile/entry`。

- [ ] **Step 5: 工作通知通道打通**

- `dingtalk_service.send_work_notification(userid, content)` 真实实现：调 `topapi/message/corpconversation/asyncsend_v2`，入参 msg.text.content。
- Phase 2 的 reporter/reminder agent 会在 DINGTALK_ENABLED 时调它，本步保证它真实发送。
- 可通过设置 `DINGTALK_NOTIFY_DRY_RUN=true` 让本地开发不真发消息（测试里就用它）。

- [ ] **Step 6: GREEN + 真机**

```powershell
python -m pytest backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_service.py backend/tests/test_agent_reporter.py backend/tests/test_agent_reminder.py -q
npm --prefix frontend test
npm --prefix frontend run build
```

真机核验：把钉钉开发者后台的 H5 微应用首页地址指向 `https://<domain>/mobile/entry`，钉钉客户端里打开能免登录直达填报页。

- [ ] **Step 7: Commit**

Commit message: `feat: 钉钉 H5 免登录与工作通知通道`

---

## Task 2: 扫码即填

**Files:**

- Modify: `backend/app/routers/mobile.py`
- Modify: `backend/app/services/mobile_report_service.py` 或新增 `services/scan_lookup_service.py`
- Modify: `backend/app/schemas/mobile.py`
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`（字段锁定逻辑）
- Modify: `frontend/src/views/mobile/OCRCapture.vue`（如果扫码复用 OCR 壳）
- New: `frontend/src/composables/useScanLookup.js`
- Test: `backend/tests/test_scan_lookup_service.py`
- Test: `backend/tests/test_mobile_scan_lookup_route.py`
- Test: `frontend/tests/coilEntryWorkbench.scan.test.js`
- Test: `frontend/e2e/mobile-scan-entry.spec.js`

- [ ] **Step 1: 写失败测试**

- `GET /api/v1/mobile/scan-lookup?qr=XT-20260503-001`：
  - 命中 `MesCoilSnapshot.qr_code`：返回 `{ source: 'coil_snapshot', header_fields: {batch_no, alloy_grade, spec_thickness, spec_width, spec_display, contract_no, current_process, next_process, material_weight}, lock_keys: [...] }`。
  - 命中 `MesCoilSnapshot.tracking_card_no`（多卷共享同一 tracking card）：返回 `source: 'tracking_card'` + 同 tracking_card_no 下首条 coil 的头字段子集。
  - 命中 `Equipment.qr_code`：返回 `source: 'machine_identity'`（字段：equipment_code, equipment_name, workshop_id），用于工人扫机台绑定。
  - 全都不命中：返回 404 `qr_not_found`。
- 扫码成功后，前端把返回的 `header_fields` 填入表单并把 `lock_keys` 里的字段置 readonly。
- 工人提交时，后端再次校验 lock_keys 的字段未被篡改（若被篡改，返回 409 `locked_field_tampered`）。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py -q
npm --prefix frontend test -- frontend/tests/coilEntryWorkbench.scan.test.js
```

- [ ] **Step 3: 实现 scan_lookup_service**

- 查找顺序：`MesCoilSnapshot.qr_code` → `MesCoilSnapshot.tracking_card_no` → `Equipment.qr_code`。
- 返回结构统一；`lock_keys` 明确列出后端期望锁死的字段名。
- 不做模糊匹配；qr 精确等值查询，命中既有索引（`mes_coil_snapshots.qr_code` / `tracking_card_no` 均已 index；`equipment.qr_code` 已 unique index）。

- [ ] **Step 4: 实现路由与篡改校验**

- `routers/mobile.py` 新增 `GET /scan-lookup`。
- `mobile_report_service` 的提交入口在保存前做一次 lock 校验：payload 里 `locked_fields_snapshot` 与提交时的 header 值比对，不一致返回 409。
- 前端在扫码成功时把 `header_fields` 一起塞到 hidden `locked_fields_snapshot` 字段。

- [ ] **Step 5: 前端接入**

- `useScanLookup.js`：封装扫码（钉钉 `dd.biz.util.scan` / 浏览器 `BarcodeDetector`）→ 调 `/scan-lookup` → 返回 `{ fields, lockKeys, source }`。
- `CoilEntryWorkbench.vue` 顶部加"扫码带出"按钮；扫码后表单自动带入头字段并锁定。
- 锁定样式用 xt-tokens 既有 readonly style；不加 description 文案。
- 非钉钉环境浏览器扫码能力不可用时，按钮隐藏；账号登录的网页用户仍可手填。

- [ ] **Step 6: GREEN + 真机**

```powershell
python -m pytest backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py backend/tests/test_mobile_submit_with_locked_fields.py -q
npm --prefix frontend test
npm --prefix frontend run e2e -- frontend/e2e/mobile-scan-entry.spec.js
npm --prefix frontend run build
```

真机核验：钉钉里打开 `/mobile/entry` → 点"扫码带出" → 用手机摄像头扫一个已登记的 QR → 头字段自动带出并锁定 → 仅需补填本工序重量/出勤 → 提交成功。

- [ ] **Step 7: Commit**

Commit message: `feat: 扫码带出卷头字段并锁定`

---

## Rollback Plan

- Task 1：`/h5-login` 端点独立，下线后前端回落到账号登录；`send_work_notification` 可通过 `DINGTALK_NOTIFY_DRY_RUN=true` 静默。
- Task 2：`/scan-lookup` 独立，下线后 `CoilEntryWorkbench.vue` 的"扫码带出"按钮隐藏，用户仍可手填；`locked_fields_snapshot` 校验为 soft（不存在时跳过）。

---

## Success Criteria

- [ ] 真实钉钉客户端中打开微应用可免登录直达填报页；账号登录仍作为 fallback。
- [ ] Phase 2 的 reporter/reminder agent 推送的工作通知能真实送达钉钉测试用户。
- [ ] 工人扫码后头字段自动带出且锁定；本工序字段可补填；提交成功写入 `MobileShiftReport`。
- [ ] Phase 1 与 Phase 2 的 success criteria 仍维持。
- [ ] 本地 `MesCoilSnapshot` 表有测试数据时，即使 `MES_ADAPTER=null`，工人的扫码填报也能跑通（投影由 Phase 1 的手填回退或手工 fixture 填）。

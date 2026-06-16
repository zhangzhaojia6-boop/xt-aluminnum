# 功能性问题深度审计 — 2026-05-27

审计范围：FastAPI 后端 + Vue3 前端 + Alembic schema + 后台调度器
审计原则：仅列出**真实功能 bug**，不包含 lint/style 类问题

---

## 严重度统计

| Severity | Count | 说明 |
|----------|------:|------|
| 🔴 Critical | 1 | 阻塞上线 |
| 🟠 High | 9 | 强烈建议修复 |
| 🟡 Medium | 18 | 应修复 |
| 🟢 Low | 7 | 建议修复 |

---

## 1. 授权与租户隔离（最高危类别）

### 🔴 1A. CRITICAL — 主数据路由（车间/班组/员工/班次配置）任何登录用户均可写
- **位置**: `backend/app/routers/master.py:93-156, 178-217, 296-327`
- `POST/PUT/DELETE /master/workshops`, `/master/teams`, `/master/employees`, `/master/shift-configs`, `/master/aliases` 仅 `Depends(get_current_user)`，多数显式 `_ = current_user` 丢弃用户。对比 `/equipment/*` 正确调用了 `_require_admin(current_user)`。
- **影响**：普通 mobile_user（如称重员）可以停用车间、改换班组归属、修改 `workshop_type`（模板/OCR 路由键）、删除员工。`workshop + team` 硬隔离从根上失效。
- **修复**：每个变更处理器加一行 `_require_admin(current_user)`（同文件 line 49 已定义）。

### 🟠 1B. HIGH — 出勤考勤读写跨租户泄漏
- **位置**: `backend/app/routers/attendance.py:51-99, 121-171, 175-220, 225-241`
- `list_schedules / list_clocks / list_results / get_result_detail / list_exceptions / resolve_exception / override_result / process_attendance` 全部 `_ = current_user`。
- `attendance_service.list_results` (`backend/app/services/attendance_service.py:355-378`) 仅按 query string 的 `workshop_id/team_id` 过滤，不按用户作用域过滤。
- **影响**：
  - 任何登录用户 `GET /attendance/results?business_date=…` 可读全厂员工出勤
  - 任何登录用户 `POST /attendance/results/{id}/override` 可篡改 `attendance_status`、`late_minutes`，无角色检查、无车间检查 — HR 级数据篡改
  - `POST /attendance/process` 任何用户可触发任意日期范围的考勤处理

### 🟠 1C. HIGH — 报表 list/detail/export/finalize 缺少作用域和角色门禁
- **位置**: `backend/app/routers/reports.py:67-99, 168-186, 189-217`
- `list_daily_reports / report_detail / export_report` 全部 `_ = current_user`，移动用户可拉全厂日报含老板摘要
- `finalize_report` 缺少 `_ensure_report_review_access` 和 `_ensure_report_publish_access`（对比 `review_report / publish_report / run_daily_pipeline` 都有检查）
- `generate_report` (line 41-60) 也无角色检查，移动用户可触发管线运行

### 🟠 1D. HIGH — imports / production_import / attendance_import / energy_import 上传无角色门禁
- `backend/app/routers/imports.py:27-44` (`/upload`)
- `backend/app/routers/production.py:43-63` (`/production/import`)
- `backend/app/routers/attendance.py:35-47, 69-81`
- `backend/app/routers/energy.py:14-23`
- 一个 weigher 可以上传 CSV，配合 `duplicate_strategy=supersede` 把任意车间的生产记录批量作废

### 🟠 1E. HIGH — production import supersede 无作用域校验，可作废其他车间数据
- **位置**: `backend/app/services/production_service.py:387-475`
- 配合 1D 的越权上传，低权限用户可批量作废其他车间数据

### 🟠 1F. HIGH — quality / reconciliation / export / imports/history / mapping-preview 忽略作用域
- `backend/app/routers/quality.py:32` (`_ = current_user`)
- `backend/app/routers/reconciliation.py:46` (`_ = current_user`)
- `backend/app/routers/export.py:28` 跨车间 CSV/XLSX 导出无角色检查
- `backend/app/routers/imports.py:55, 68, 79` 全厂导入历史可见

### 🟡 1G. MEDIUM — qr-login virtual_role_qr 无同意自动创建账号
- **位置**: `backend/app/routers/auth.py:108-148`
- `equipment.equipment_type == 'virtual_role_qr'` 时直接 `User(...is_mobile_user=True, role=mapped_role)` 然后发 JWT
- 拍 QR 或猜中 `equipment.qr_code` 即获车间永久身份；QR 无过期、无速率限制；`equipment.qr_code` 在模型上无 UNIQUE 约束

### 🟡 1H. MEDIUM — realtime/aggregation/live/active-date 丢弃用户
- **位置**: `backend/app/routers/realtime.py:178` — `del current_user`
- 返回的 `business_date` 全局，跨车间信息泄漏（影响小，但同模式）

---

## 2. 数据完整性

### 🟠 2A. HIGH — `ShiftProductionData.version_no` 存了但从未做乐观锁
- **位置**: `backend/app/services/production_service.py:472-549` (`update_shift_data_status`)
- 读实体 → 改 `data_status` → 审计 → commit，没有 `WHERE version_no = N` 守卫，没有 `version_no += 1`
- 两个审核员并发 `/confirm` 和 `/reject` 竞态，最后写入获胜，工作流事件触发两次，`bulk_update_production_exception_status` 跑两次
- `version_no` 仅在 import-supersede (line 437) 增加

### 🟠 2B. HIGH — 登录 fallback 在生产环境从环境变量自动创建管理员（后门）
- **位置**: `backend/app/routers/auth.py:23-36`
```python
user = db.query(User).filter(User.username == body.username).first()
if not user and body.username == settings.INIT_ADMIN_USERNAME and body.password == settings.INIT_ADMIN_PASSWORD:
    user = User(... role='admin' ..., is_active=True)
    db.add(user); db.commit()
```
- 操作员删除/改名管理员后，下次用环境变量值登录会**静默重建一个完整 admin**
- 用 `==` 明文比较（非常量时间）
- 即使原 admin 被停用，也会绕过 `is_active` 检查重建
- `validate_runtime_settings` 警告弱默认密码但**不禁用此 fallback**

### 🟡 2C. MEDIUM — 唯一约束未考虑可空字段（NULL distinctness）
- **位置**: `backend/app/models/production.py:80-100, 124-145`
- `MobileShiftReport.uq_mobile_shift_reports_key` = `(business_date, shift_config_id, workshop_id, team_id)`，`team_id` 可空 → 同班次同车间同日两条 `team_id=NULL` 报告可共存（PG 视 NULL 互不相同）
- `MobileReminderRecord.uq_mobile_reminder_records_key` 含可空 `team_id` 和 `leader_user_id`
- `ShiftProductionData.uq_shift_production_active_key` 部分索引中 `equipment_id` 可空，同问题
- **修复**：用 `COALESCE(team_id, 0)` 表达式索引或 `NULLS NOT DISTINCT`（PG15+）

### 🟡 2D. MEDIUM — Decimal/float 混用导致重量与金额精度丢失
- 模型用 `Numeric(14, 3)` 但 services 到处转 float：`_to_float`、`_to_number`（`production_service.py:238-250`）、`mobile_report/lifecycle.py:_to_float`
- 100+ 班次累加，浮点误差累积
- `executive.py:152-170` 返回 `fee_per_ton: float`，客户端往返有损
- `mobile_report/summary.py:create_coil_entry` 废品重 `float(...)` 算术然后 `round(..., 2)` 写回 Decimal — 上千卷后漂移

### 🟡 2E. MEDIUM — 多步编排无原子性
- **位置**: `backend/app/main.py:84-122` (`_run_orchestration_pipeline`)
- session1 → aggregator commit；session2 → reporter commit；reporter 失败则只有部分聚合无日报，无补偿动作
- 无 `target_date` 的幂等 key，重跑会覆盖
- 同模式见 `_run_executive_daily_snapshot` (line 196-214)：单 session 内 cost_aggregator flush + profit_snapshot commit，profit_snapshot 异常 → session rollback 把 cost_aggregator 也清掉

### 🟡 2F. MEDIUM — master.py POST/PUT 先 commit 后审计；审计失败造成孤行
- **位置**: `backend/app/routers/master.py:96-119, 165-188, 248-273`
- 模式 `db.add → db.commit → db.refresh → log_action`
- `log_action` 失败（`auto_commit=True` 第二次 commit 因完整性出错），workshop 已创建但缺审计 — "每个变更必有日志"不变量被破坏

---

## 3. 状态机

### 🟠 3A. HIGH — `_status_transition_guard` 允许非法跳转
- **位置**: `backend/app/services/production_service.py:462-470`
- 非法但被允许的转换：
  - `confirmed → rejected`（发布就绪后降级）
  - `rejected → confirmed`（跳过复审）
  - `auto_confirmed → confirmed`（guard 没考虑此状态，未拒绝）
  - `published → rejected`（无 published 子句）
  - 任意 → `void` 对管理员开放，但 `update_shift_data_status` 不要求行先到终态 — 管理员可作废未审核的 pending 行隐藏数据无历史

### 🟡 3B. MEDIUM — `MobileShiftReport.report_status` submit 转换无守卫
- **位置**: `backend/app/services/mobile_report/lifecycle.py:save_or_submit_report`
```python
if submit:
    report.report_status = 'submitted'
else:
    if report.report_status not in {'returned', *APPROVED_REPORT_STATUSES}:
        report.report_status = 'draft'
```
- 已 `approved` 或 `auto_confirmed` 的报告可被 `submit=True` 重置为 `submitted` — `_sync_to_shift_production` 会清空 `reviewed_by/confirmed_by/published_at` 并将 `data_status='pending'`
- 班长可通过重新提交回滚已批准的行

### 🟡 3C. MEDIUM — `sync_mobile_status_from_review` 盲覆盖状态
- **位置**: `backend/app/services/mobile_report/lifecycle.py` (~line 818)
- 不论报告当前状态（含终态如 `voided`）都覆写

### 🟡 3D. MEDIUM — 出勤确认锁检查用 role 字符串而非作用域
- **位置**: `backend/app/services/attendance_confirm_service.py:391-393`
```python
elif confirmation.status in {'confirmed', 'hr_reviewed'} and current_user.role != 'admin':
    raise _http_error('attendance confirmation is already locked')
```
- role 字符串相等跳过角色层级；其他车间的 admin 可重确认任意班组的确认无 `override_reason` 审计

---

## 4. API 契约

### 🟡 4A. MEDIUM — `MobileShiftReport.attendance_count` 声明 `int|None`，service 不强制
- `payload.get('attendance_count')` 直接写入；schema 漏检的字符串导致 SQLAlchemy 绑定失败，整个 submit 报错且无诊断

### 🟢 4B. LOW — `mobile.report_history` 的 `limit` 无上界
- **位置**: `backend/app/routers/mobile.py:115-127`
- `limit: int = 10` 无 `Query(le=...)`；service 内 `min(limit, 30)` 安全，但契约与文档不一致

### 🟢 4C. LOW — `executive.update_processing_fee` 不校验 effective 区间
- `effective_to >= effective_from` 未校验

---

## 5. 集成

### 🟠 5A. HIGH — MES 重试配置是死代码
- **位置**: `backend/app/services/mes_sync_service.py:434-470`
- `settings.MES_SYNC_RETRY_LIMIT` 和 `settings.MES_SYNC_BACKOFF_SECONDS` 在 `config.py:246-250` 校验但代码中**从未引用** — 没有重试循环
- 单次 TLS 失败/5xx 即标记 `failed`，等下一个 poll 间隔（默认 1 分钟）
- 重试变量在 runbook 写了，代码没实现

### 🟡 5B. MEDIUM — `RestApiMesAdapter._default_sender` 每次请求新建 `httpx.Client()`
- **位置**: `backend/app/adapters/rest_api_mes_adapter.py:174-177`
- 每个请求新 TCP+TLS 握手，`MES_SYNC_LIMIT=200` 时 8 秒超时常因延迟用尽
- **修复**：用长寿命 client

### 🟡 5C. MEDIUM — DingTalk auth code 重放在我方层未防御
- **位置**: `backend/app/routers/dingtalk.py:85-148`、`dingtalk_service.exchange_code`
- `code` 走 query param 发到钉钉，无 nonce/state 与用户/会话绑定
- 完全依赖钉钉服务端拒绝重用 code；网络抖动加日志记录 = 账号接管风险

### 🟡 5D. MEDIUM — DingTalk 端点在 FastAPI sync handler 内用阻塞 `urllib.request.urlopen`
- **位置**: `backend/app/routers/dingtalk.py:39-42, 67-70`、`dingtalk_service.py:230-233`
- 每个调用阻塞 worker 线程最多 15s（service 内 20s）
- 钉钉慢响应 + 无重试 = 维护窗口期 uvicorn worker 饱和 DoS

### 🟢 5E. LOW — WeCom 群机器人无出站签名、无入站验证（无入站存在）
- 集成规范有提入站；如增需实现 URL 签名

### 🟢 5F. LOW — `wecom_bot_workshop_webhook_map` 无 SSRF 防御
- 错误配置可指向内部服务；validator 仅检 JSON shape

---

## 6. 后台任务

### 🟠 6A. HIGH — 日快照用 `date.today()` 但调度器在 `Asia/Shanghai`
- **位置**: `backend/app/main.py:182-217`
```python
scheduler = BackgroundScheduler(timezone=settings.DEFAULT_TIMEZONE)  # Asia/Shanghai
def _run_executive_daily_snapshot():
    target = _date.today() - _td(days=1)   # 用本地服务器时间，不是 scheduler tz
```
- 容器 UTC 时（Docker 典型），cron `hour=0, minute=45` 上海时间 = UTC 16:45 前一天，`date.today()` 仍返回上海昨日 = `D-1` UTC，再减 1 = `D-2`
- "昨天的高管快照"实际上算的是前天
- `_run_aluminum_price_fetch` (line 188-198) 同问题
- **修复**：用 `health_service.current_business_date()`（line 78 已用过）

### 🟡 6B. MEDIUM — Pipeline 任务每个 agent 各自 commit，部分成功留下不一致
- 见 2E

### 🟡 6C. MEDIUM — `_run_mes_sync` 吞所有异常永不告警
- **位置**: `backend/app/main.py:131-141`
- 配合 5A（无重试），MES 集成可静默死亡直到有人看日志

### 🟢 6D. LOW — `reminder_sweep` 不分工作时段 30 分钟一次
- **位置**: `backend/app/main.py:172-181`
- 周末和半夜也催报；`_is_quiet_hour` 在 `ai_briefing_service` 存在但未应用到提醒
- 凌晨 3 点骚扰工人钉钉

---

## 7. Auth / 安全

### 🟠 7A. HIGH — `INIT_ADMIN_PASSWORD` 兼任后门
- 见 2B

### 🟡 7B. MEDIUM — Realtime SSE 的 `last_event_id` query 可被任意篡改
- **位置**: `backend/app/routers/realtime.py:140-152`
- `cursor` 来自 query string 或 `Last-Event-ID`，无签名，无"用户加入时间之后"的检查
- 用户可 `last_event_id=0` 重放所有车间历史事件（48 小时缓存窗口）
- **修复**：限制 `last_event_id` 不早于用户认证时间

### 🟡 7C. MEDIUM — SSE 每连接 DB 轮询，无共享订阅
- **位置**: `backend/app/core/event_bus.py:DatabaseEventBus._fetch`
- 每次 poll（0.2s）开新 session
- N 个并发 SSE = ~5N queries/sec 打 `realtime_events`
- 单用户限速 2，全厂无上限，无背压

### 🟢 7D. LOW — 密码哈希 rounds 用默认
- `pbkdf2_sha256` 默认 29000 轮；2026 年偏低端
- 新部署考虑 Argon2id

### 🟢 7E. LOW — CORS 启动时不校验
- `validate_runtime_settings` 不校验 CORS_ORIGINS
- 用 localhost 默认部署到生产 + `allow_credentials=True`，浏览器会拒，但启动无报错

---

## 8. Realtime / SSE

### 🟡 8A. MEDIUM — Permit 早期断开泄漏（竞态窗口）
- **位置**: `backend/app/routers/realtime.py:_event_stream` (line 99-128)
- `event_bus.listen(...)` 抛出意外异常时，generator 可能被异步 GC 在 `finally` 之前
- **修复**：在 `event_bus.listen` 周围加显式 try/except 防御性 release

### 🟢 8B. LOW — SSE 首帧竞态：`yield 'retry: 1000\n\n'` 后立即进 DB poll 循环
- 新部署 pod，DB 短暂不可用时 SSE 已发 200 + retry，客户端无限 1 秒重连
- **修复**：先 fast `_fetch` 探测，DB 不可达返 503

---

## 优先级修复建议

### 本周必修（4 项）
1. **1A** — 主数据路由全部加 `_require_admin`（每处一行变更）
2. **1B + 1C + 1D + 1F** — 同模式 `_ = current_user` 横扫式修复，最大隔离漏洞
3. **2B** — 删除 `auth.login` 自动创建 admin fallback，或加 `APP_ENV=development` 门禁
4. **6A** — 日快照时区 bug，`date.today()` 改 `health_service.current_business_date()`

### 本月内修
5. **3A** — 状态机非法转换守卫
6. **2A** — `version_no` 乐观锁
7. **2C** — 唯一约束 NULL 处理
8. **5A** — MES 重试逻辑实装
9. **2E + 6B** — 编排管线幂等与原子性

### 季度规划
- **2D** — Decimal 全链贯通，移除浮点中间态
- **7B/7C** — SSE 安全与共享订阅重构
- **5B/5D** — 出站集成异步化、长寿命 client

---

## 附录：审计方法

- 后端：阅读 `backend/app/routers/*.py`、`backend/app/services/*.py`、`backend/app/models/*.py` 关键路径
- 前端：仅 SSE 客户端 (`frontend/src/composables/useRealtimeStream.js`)
- 调度：`backend/app/main.py:lifespan`
- 不审 lint/style/未用导入；那些已在另一份代码体检报告中

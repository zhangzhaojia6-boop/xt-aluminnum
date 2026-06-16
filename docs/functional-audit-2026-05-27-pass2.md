# 功能性问题深度审计第二轮 — 2026-05-27

第一轮覆盖了授权/隔离、登录后门、状态机、MES 重试、SSE 重放、时区。本轮聚焦：
前端、数据库性能、数值与计算正确性、文件处理、迁移安全、LLM 集成、审计可观测性、边缘鲁棒性。

新增 **48 个发现**（去重后 41 个独立问题），其中 3 个 **P0 数据正确性** bug。

---

## 严重度统计（第二轮）

| Severity | Count | 主要类别 |
|----------|------:|---------|
| 🔴 **P0** | 3 | 数值算错（成本/利润/人工）、调度器多副本重复执行 |
| 🟠 P1 | 13 | 数据丢失、token 泄漏、迁移竞态、性能阻塞 |
| 🟡 P2 | 18 | 性能、PII、CSP/CSRF、审计断链 |
| 🟢 P3 | 7 | 边缘鲁棒性 |

---

## 🔴 P0 — 数据已经在错（必须本周修）

### F17 — 利润快照 kg/吨 单位混用，营收 1000 倍偏差
**位置**: `backend/app/agents/profit_snapshot.py:73-77`
```python
output_kg = workshop_output[r.workshop_id]   # 注释说 kg，实际是 ton
output_tons = output_kg / Decimal('1000')    # 多除 1000
```
- `MobileShiftReport.output_weight` 上游处处当吨用（`report_service`、`aggregator.py`、`factory_command_service.py:837` `_local_weight_tons`）
- 仅 `data_source == 'mobile_coil_agg'` 才需要 ÷1000（`mobile_report/summary.py` 卷级聚合是 kg）
- 该函数 **无条件 ÷1000** → 营收下降 1000 倍 → **总利润完全错误**

**影响**：高管驾驶舱 P&L 静默错算 1000 倍。可能正负翻转，触发"亏损"误报。

---

### F18 — 三班制人工成本被多算 3 倍
**位置**: `backend/app/agents/cost_aggregator.py:65-78`
```python
if r.attendance_count is not None:
    ws['attendance'] += int(r.attendance_count)   # 跨所有班次累加
...
labor_cost = Decimal(str(attendance)) * LABOR_COST_PER_HEADCOUNT_PER_DAY
```
- `attendance_count` 是**单班次**人数，循环把当天所有班次（早、中、夜）的人数都累加
- `LABOR_COST_PER_HEADCOUNT_PER_DAY` = 350 元/人天
- 三班制车间 → 100 人天被算成 300 人天 → 多 7 万/车间/天

**影响**：每日成本快照 `MachineDailyCostSnapshot.labor_cost` 系统性高估，毛利严重低估。

---

### F43 — APScheduler 在每个 worker × 每个副本上重复执行
**位置**: `backend/app/main.py:29, 67, 263`
```python
scheduler = BackgroundScheduler(timezone=settings.DEFAULT_TIMEZONE)
...
scheduler.start()  # 每个 worker 进程启动时都会跑
```
- `docker-compose.prod.yml` 用 `--workers 4` → 单容器 4 个 scheduler 实例
- K8s 多副本 → N×4 个 scheduler
- `_run_executive_daily_snapshot` 凌晨 00:45 触发 → 同时 4N 次执行
- `cost_aggregator.py:81-86` 的 `existing` 检查没有 `SELECT FOR UPDATE` → 并发覆盖
- 配合 F17/F18，错乱数字还会被多副本写多次

**影响**：成本/利润数据被 4N 次重复计算。pgsql 唯一约束阻止部分重复但不阻止竞态读写。

**修复方向**：要么 leader-election（`apscheduler.jobstores.SQLAlchemyJobStore` + `coalesce`），要么把调度器拆到独立 sidecar 进程只跑一次。

---

## 🟠 P1 — 数据丢失/泄漏/性能阻塞

### F1 — 前端 token 存 sessionStorage，钉钉 H5 每个 webview 重新登录
**位置**: `frontend/src/stores/auth.js:6-10, 105-112`
- `TOKEN_KEY` 用 `sessionStorage`，每个新 tab/webview 一份
- 钉钉内嵌浏览器频繁开新 webview → "请重新登录" 反复弹
- `useLocalDraft.js` 同时用 `localStorage`，造成草稿存活但 token 失效 → 草稿孤儿

**影响**：现场工人体验灾难。

---

### F3 — 管理员降级用户后，前端权限不刷新
**位置**: `frontend/src/stores/auth.js:138-147`
- `fetchProfile()` 仅在 `auth.user` 为空时被调用
- 被降级用户继续看到 admin tab，直到手动登出
- 后端写操作被拦截，但**读取仍泄漏**（主数据、审计列表等）
- 没有 `/users/me` 轮询、没有 token 版本检查、SSE 没有 `permissions_changed` 事件

---

### F5 — 重试队列**静默丢弃**所有非网络错误的离线提交
**位置**: `frontend/src/composables/useRetryQueue.js:240-252`
```python
} catch (error) {
  if (isRetryableNetworkError(error)) break
  await deletePendingRecord(record.id)   # 422、500、任何 HTTP 错都直接删
}
```
- 工人离线填报 → 联网后服务器 422（投入<产出） → 数据被删，无 toast、无日志
- **离线优先工作流的核心数据丢失**

---

### F6 — 文件上传**仅前端校验**，无服务端大小限制
**位置**: `frontend/src/views/imports/FileImport.vue:33-38` 和 `backend/app/services/import_service.py:186-198`
- 前端只检查 `accept=".csv,.xlsx"`，无大小限制
- 后端 `_save_upload_file` 也只看后缀，pandas 解析任意文件
- 攻击者可上传多 GB xlsx → 直接 OOM worker
- 配合 F19（无行数上限）= xlsx-bomb 攻击

---

### F11 — 实时面板加载时 `db.query(MesCoilSnapshot).all()` 全表加载
**位置**: `backend/app/services/realtime_service.py:1415-1420`
- 加载整张 `mes_coil_snapshots` 表到内存，再 Python 端过滤 `business_date != target_date`
- 同步运行 6 个月后，表有数百万行 → 工厂指挥页加载内存爆炸

**修复**：SQL `WHERE business_date = ?` 直接做。

---

### F13 — `/readyz` 探活做全表扫描
**位置**: `backend/app/services/config_readiness_service.py:73-84, 430, 463`
- `db.query(User).all()` 加载所有用户
- `db.query(AttendanceSchedule).all()` — 1000 工人 × 30 天排班 = 30k 行
- k8s 探活每 5-10s 一次 → DB CPU 拉满

---

### F19 — Excel/CSV 导入**无行数上限**
**位置**: `backend/app/services/import_service.py:155-169`
- `pd.read_excel(path)` 一次性读入整个 xlsx
- 1M 行 xlsx 直接 OOM worker
- 同样问题在 `import_attendance_schedules`、`import_clock_records`、`import_energy_data`

---

### F20 — 对账把零产出日全部标记为异常（噪音淹没真异常）
**位置**: `backend/app/services/reconciliation_service.py:267-287`
```python
if energy_total == 0.0 or output_weight == 0.0:
    created.append(_create_item(...))
```
- 维护班次合法 0 产出但有待机电耗 → 创建对账异常，`diff_value = energy - 0`（且单位混用 kWh vs 吨）
- 每周末后异常数爆炸，淹没真正的对账问题

---

### F31 — 多副本启动时 `alembic upgrade head` 竞态
**位置**: `docker-compose.prod.yml:24-29`
```yaml
command: alembic upgrade head && python init_master_data.py && ... uvicorn --workers 4
```
- 多副本同时启动 → 多个 `alembic upgrade` 并发，无 `pg_advisory_lock`
- `init_real_master_data.py` 每副本都跑 → 重复键
- 部署在 N 副本时反复重启直到一个胜出

---

### F32 — 0026 迁移**静默 NULL 化**重复钉钉绑定
**位置**: `backend/alembic/versions/0026_unique_user_dingtalk_bindings.py:41-69`
- 找到重复 `dingtalk_user_id`，保留 `is_active=true` 的 + `MIN(id)`，**其他全部置 NULL**
- 没有审计、没有备份
- 真实双绑用户被静默断绑 → 钉钉登录失败

---

### F35 — 钉钉 access_token 进入异常日志
**位置**: `backend/app/services/dingtalk_service.py:285, 529, 534`
```python
url=f'https://oapi.dingtalk.com/...?access_token={parse.quote(access_token)}&...'
...
except Exception as exc:
    logger.warning('DingTalk work notification failed: %s', exc)  # exc 含 url 含 token
```
- `httpx.HTTPStatusError.__str__()` 包含完整 URL → ELK/Sentry/file logs 全有钉钉 access_token
- token 30 分钟有效，足够攻击者用

**修复**：日志输出前必须 strip query string。

---

### F41 — 编排管线异常被 `logger.exception` 吞掉，无告警
**位置**: `backend/app/main.py:103-126`
- aggregator/reporter 每阶段失败仅 log，无 `event_bus.publish('pipeline_failed')`、无 audit
- 静默死亡 3 天没人发现，直到日报缺失

---

### F45 — 负数重量被持久化（仅生成异常但不拒绝）
**位置**: `backend/app/services/exception_service.py:158-167`
- 负值生成 `'abnormal_value'` 异常，但**行仍写入**
- 下游 `cost_aggregator` 把负 `gas_daily` 累加 → 燃气成本变负 → 总成本被错误降低

---

## 🟡 P2 — 应修复

### F2 — 路由守卫并发竞态
`frontend/src/router/index.js:236-254` `fetchProfile()` 无 in-flight 缓存，并发跳转重复请求 `/users/me`，可能在 token 已设但 user 仍 null 时放行。

### F4 — SSE token 轮换触发**重放风暴**
`frontend/src/composables/useRealtimeStream.js:200-214` `watch(authStore.token)` 重置 `lastEventId = ''` → 每次重连从 id=1 重放全部事件。

### F9 — SSE 数据库轮询负担
`backend/app/core/event_bus.py:127-152` 每个 SSE 客户端 200ms 轮询一次，N 客户端 = 5N qps。

### F10 — quality_service 能耗校验 N+1 查询
`backend/app/services/quality_service.py:285-306` 每个 (workshop, shift) 桶都跑 3 表关联子查询。

### F12 — `WorkOrder.all()` 全表加载
`backend/app/services/realtime_service.py:1372` 每次实时面板请求都全表扫描 `work_orders`。

### F21 — `gross_margin_pct` 无边界
`backend/app/agents/profit_snapshot.py:122-127` 可超 100% 或负值，配合 F17 完全失真。

### F22 — 人头计数三处真相不一致
- `production_service.py:78-115` 从考勤推算
- `MobileShiftReport.attendance_count` 工人手填
- `cost_aggregator` 用 attendance_count
三个数据源进入不同 KPI，互相打架。

### F24 — 铝价跨日竞态
`backend/app/agents/aluminum_price_fetcher.py:58, 62` cron 10:30 跑，但 `_run_executive_daily_snapshot` 凌晨 00:45 用昨日价 → 周二早上算昨天利润时拿不到周一价格，用周五的。

### F25 — OCR 无像素维度上限
`backend/app/services/ocr_service.py:64-73` `cv2.imdecode` 对 100k×100k 像素图分配 W×H×3 字节 → OOM。

### F26 — 原始文件名进入审计日志/导出
`backend/app/services/mobile_report/lifecycle.py:464-466` `report.photo_file_name` 接受用户控制的文件名（含换行、NUL、`=cmd|/c calc!A1`） → Excel 导出公式注入。

### F27 — 上传文件无清理
`backend/app/services/import_service.py:194-198` 失败/作废批次的临时文件永远滞留，`/uploads` 目录不断膨胀，且作为静态目录可被遍历访问。

### F29 — CSV 编码硬编码 utf-8-sig
`backend/app/services/import_service.py:158-161` 没有 GBK fallback，国产 MES 导出的 GBK CSV 直接 500。

### F30 — 迁移版本号混乱
`0001_initial → 001 (placeholder) → 0002_*` 命名相似，未来合并极易冲突。

### F33 — 索引创建未用 CONCURRENTLY
`0027/0028/0029` 直接 `CREATE INDEX` → 持有 `ACCESS EXCLUSIVE` 锁，部署期间表写阻塞。

### F34 — LLM 提示注入
`backend/app/services/assistant_service.py:146-158, 374-385` 用户 query/prompt 直接 f-string 拼进 system prompt，无边界符。攻击者可输入 "忽略上面所有指令..." 接管输出。

### F37 — LLM 调用无 max_tokens / 成本封顶
`backend/app/adapters/llm.py:189-198` 仅传 temperature，长上下文调用 + 重试 = 账单失控。

### F38 — PII 直发 LLM
`backend/app/services/leader_summary_service.py:101-105` 发送的 metrics 含 anomaly_digest（员工姓名、异常原因），无脱敏。火山豆包 = 字节跳动，PIPL/GDPR 边界不明。

### F39 — 审计 `record_id` 仅接受 int
`backend/app/services/audit_service.py:26-32` 业务日期键的实体（如 `entity_id="2025-01-15"`）`record_id=None` → 无法溯源。

### F40 — 审计与业务写不在同事务
`audit_service.py:51-57` `auto_commit=True` 已经 commit；后续业务异常 rollback **不会回滚审计** → 审计说"X 已作废"但实际没作废。

### F42 — 限流是进程级，多副本失效
`backend/app/core/rate_limit.py:90-95` `SlidingWindowRateLimiter` 是 in-memory，4 worker × N 副本 → 实际限流是配置的 4N 倍。

### F47 — 0026 迁移 UPDATE 不分批
3 个 `UPDATE users` 串行，第三个还有相关子查询，10 万用户行级锁住几分钟。

---

## 🟢 P3 — 鲁棒性建议

| # | 位置 | 问题 |
|---|------|------|
| F7 | reference-command/CommandLogin.vue:6 | v-html 风险（已删除目录但提示模式） |
| F8 | api/index.js | 服务端 detail 直接弹 toast，社工攻击面 |
| F14 | imports.py:55-58 | `query.count()` 全表扫 |
| F16 | energy_service.py:206-219 | 单请求 4 次 Workshop 全表加载 |
| F23 | aggregator.py:191 | `int(actual_headcount)` 截断小数 |
| F36 | assistant_service.py:330-336 | LLM 响应无 schema 校验 |
| F44 | factory_command_service.py | 多处 `sum()/N` 未防 N=0 |
| F46 | exception_service.py:185 | `business_date < today` 用本地 today，跨午夜误报 |
| F48 | aluminum_price_fetcher.py:73 | 文档说"多源兜底"，实际只有 sina 一个源 |

---

## 系统性结论

### 三个真正吓人的发现

1. **F17 + F18 → 高管驾驶舱的 P&L 是错的**。营收差 1000 倍、人工成本差 3 倍，互相抵消可能让数字看起来"差不多对"，但任何决策都是基于错误数字。
2. **F43 → 多副本上线那天就开始重复扣分**。每个数据点被 4-12 倍写入。
3. **F31 + F32 → 部署本身就有破坏性**。alembic 无锁竞态 + 钉钉绑定静默 NULL 化。

### 重量单位之根：项目缺乏单一约定

- 数据库列叫 `Numeric(14,3)` — 不知道是 kg 还是吨
- 移动端 `<el-input placeholder="投入量" />` — 没标注单位
- 部分聚合路径当吨，部分当 kg
- `data_source == 'mobile_coil_agg'` 这一个分支单独除 1000，其他分支不除 → 所有跨路径累加都可能错

**根本修复**：模型字段重命名为 `output_weight_kg`（或 `_tons`），全代码搜索替换。前端表单加固定单位提示。

### 推荐的修复顺序

**第 0 周（紧急）**：
- F17 利润单位修正
- F18 人工成本去重
- F43 调度器单实例化（环境变量门禁 + 主选举）
- F35 钉钉 token 日志脱敏

**第 1 周**：
- F31 alembic 加 advisory lock
- F32 0026 迁移补审计/备份
- F45 负数重量 schema 拒绝
- F5 重试队列错误兜底
- F1 token 改 localStorage

**第 2-4 周**：性能修复（F11、F13、F19）+ 审计完整性（F39、F40、F41）

---

## 与第一轮的关系

第一轮报告了 35 项授权/隔离/状态机问题；本轮 41 项独立问题，**总计 76 项**（有 1 项 F4 与第一轮 7B 在同一组件不同切面）。

合并视图请同时阅读：
- `docs/functional-audit-2026-05-27.md`（第一轮）
- `docs/functional-audit-2026-05-27-pass2.md`（本轮）

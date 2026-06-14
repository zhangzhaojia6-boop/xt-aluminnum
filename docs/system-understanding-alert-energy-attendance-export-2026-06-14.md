# 鑫泰铝业 数据中枢：异常、能耗、考勤、缺报导出链路理解

日期：2026-06-14
范围：管理端 `/manage/alerts`、`/manage/energy`、`/manage/attendance`，以及缺报 Excel 导出。

## 1. 本轮结论

- `/manage/energy` 当前线上可用，读取的是后端 `/api/v1/energy/summary` 汇总结果。
- 能耗老导入接口 `/api/v1/energy/import` 已停用，返回 410；当前主链路来自电工填报、内勤填报、物联网影子表，以及 MES 包装产量分母兜底。
- `/manage/alerts` 是一个聚合页，前端并不只读一个异常表，而是同时读取生产看板、质量问题、对账问题、MES 填报差异、实时缺报。
- `/manage/attendance` 当前是“考勤预留 / 结果核查”页面，但页面上仍有“自动处理”按钮，会调用写入型接口 `/api/v1/attendance/process`。
- 缺报 Excel 导出线上可用，会导出缺报明细、待归属明细、车间汇总、MES 异常明细四个工作表。
- 已修复一个真实问题：异常页请求质量问题和对账问题时原先传 `target_date`，但后端对应接口只识别 `business_date`，会导致异常页可能显示旧日期的质量/对账问题；当前前端已改为向质量和对账接口传 `business_date`。

## 2. 页面到接口

### `/manage/alerts`

前端页面：

- `frontend/src/views/manage/alerts/AlertsPage.vue`
- `frontend/src/composables/useAlertsTimeline.js`
- `frontend/src/components/manage/_alertEventNormalize.js`

页面读取五类数据：

- 生产异常：`GET /api/v1/dashboard/factory-director?target_date=YYYY-MM-DD`
- 质量问题：`GET /api/v1/quality/issues?target_date=YYYY-MM-DD`
- 对账问题：`GET /api/v1/reconciliation/items?target_date=YYYY-MM-DD&status=open`
- MES 填报差异：`GET /api/v1/aggregation/live/mes-fill-gaps?business_date=YYYY-MM-DD`
- 实时缺报：`GET /api/v1/aggregation/live?business_date=YYYY-MM-DD`

注意：

- 生产看板接口确实使用 `target_date`。
- MES 和实时聚合接口使用 `business_date`。
- 质量和对账后端接口实际只认 `business_date`，这里前端参数名目前不一致。

### `/manage/energy`

前端页面：

- `frontend/src/views/energy/EnergyCenter.vue`
- `frontend/src/api/energy.js`

接口：

- `GET /api/v1/energy/summary?business_date=YYYY-MM-DD`
- `POST /api/v1/energy/import` 已停用，返回 410。

后端入口：

- `backend/app/routers/energy.py`
- `backend/app/services/energy_service.py`

能耗汇总优先级：

- 电工填报：`mobile_shift_reports` 和 `machine_energy_records`
- 内勤每日一录：`work_order_entries.extra_payload`
- 旧导入记录：`energy_import_records`
- 物联网影子数据：`iot_energy_snapshots`
- 产量分母兜底：优先 MES 包装/入库产量，再回退人工入库/包装数据。

### `/manage/attendance`

前端页面：

- `frontend/src/views/attendance/AttendanceOverview.vue`

接口：

- `GET /api/v1/attendance/results?business_date=YYYY-MM-DD`
- `GET /api/v1/attendance/summary?business_date=YYYY-MM-DD`
- `POST /api/v1/attendance/process`
- `GET /api/v1/attendance/results/{employee_id}/{business_date}`
- `GET /api/v1/attendance/exceptions?business_date=YYYY-MM-DD`

注意：

- 导入排班和导入打卡接口已经停用，均返回 410。
- 移动端考勤确认另走 `/api/v1/attendance/draft`、`/api/v1/attendance/confirm`、`/api/v1/attendance/anomalies`。
- 管理端考勤页面文字写的是“仅保留结果核查入口”，但按钮仍可触发自动处理，这是后续产品和权限审查要重点确认的点。

### 缺报 Excel

后端入口：

- `backend/app/routers/realtime.py`
- `backend/app/services/missing_report_export_service.py`

接口：

- `GET /api/v1/aggregation/live/missing-report-export?business_date=YYYY-MM-DD`

导出内容：

- `缺报明细`
- `待归属明细`
- `车间汇总`
- `MES异常明细`

导出数据来源：

- 实时聚合：`realtime_service.build_live_aggregation`
- 待归属：`realtime_service.build_pending_assignment_detail`
- MES 差异：`mes_fill_gap_service.build_mes_fill_gaps`

## 3. 线上只读验证

验证日期：`2026-06-13`

接口验证结果：

- 登录：`admin` 管理员账号验证成功；文档不保存明文密码。
- `/api/v1/energy/summary`：200，返回 7 条。
- `/api/v1/attendance/results`：200，返回 0 条考勤结果。
- `/api/v1/attendance/summary`：200，返回 33 条移动端考勤确认摘要。
- `/api/v1/dashboard/factory-director`：200，可返回日报/看板汇总。
- `/api/v1/quality/issues?target_date=2026-06-13`：200，返回 6 条，但日期实际为 `2026-05-21` 和 `2026-05-25`。
- `/api/v1/quality/issues?business_date=2026-06-13`：200，返回 0 条。
- `/api/v1/reconciliation/items?target_date=2026-06-13&status=open`：200，返回 0 条。
- `/api/v1/aggregation/live/mes-fill-gaps`：200，返回 195 条，其中包含已匹配和未匹配状态。
- `/api/v1/aggregation/live`：200，返回 13 个车间，填报总单元 144，缺报单元 111。
- `/api/v1/aggregation/live/missing-report-export`：200，导出文件约 24 KB。

导出工作表行列：

- `缺报明细`：9 列，约 127 行非空数据。
- `待归属明细`：19 列，约 4 行非空数据。
- `车间汇总`：8 列，约 15 行非空数据。
- `MES异常明细`：11 列，约 197 行非空数据。

浏览器验证：

- `/manage/alerts`：最终加载出 177 件异常，其中质检 6、填报 22、MES 149。
- `/manage/energy`：显示 7 条能耗明细，电耗 6512、气耗 18913、产量 241.91 吨、单吨峰值 105.1。
- `/manage/attendance`：页面可打开，默认看 2026-06-14，当前显示 0 人。

## 4. 已修复问题和仍需关注风险

### 已修复 1：异常页质量/对账参数名错接

问题：

- 前端异常页传 `target_date`。
- 后端 `/quality/issues` 和 `/reconciliation/items` 只识别 `business_date`。

影响：

- 异常页可能把历史质量问题显示到当前日期。
- 这会让用户误以为今天仍有旧问题未处理。

证据：

- `GET /quality/issues?target_date=2026-06-13` 返回 6 条，日期为 `2026-05-21` 和 `2026-05-25`。
- `GET /quality/issues?business_date=2026-06-13` 返回 0 条。

建议：

- 已改前端 `useAlertsTimeline.js`：质量和对账接口改传 `business_date`。
- 已增加前端测试：异常页加载指定日期时，质量/对账请求必须带 `business_date`。
- 后端后续也可兼容 `target_date`，避免旧前端或历史入口继续错用。

### 风险 1：考勤页面“预留”与“自动处理”行为不一致

问题：

- 页面文案说“仅保留结果核查入口”。
- 页面仍有“自动处理”按钮，调用 `/attendance/process`。

影响：

- 用户可能误点触发考勤结果生成。
- 如果未来接入钉钉，权限和操作边界必须重新确认。

建议：

- 如果考勤暂未正式启用，自动处理按钮应只对管理员或测试环境开放。
- 或把页面文案改成“可核查并手动处理考勤结果”，避免误导。

### 风险 2：异常页初次快速切页会出现请求中断噪声

问题：

- 快速从异常页切到别的页面时，浏览器会看到 `net::ERR_ABORTED`。

影响：

- 这通常是页面切换导致的中断，不等于后端接口失败。
- QA 记录时需要区分“切页噪声”和真正 4xx/5xx。

建议：

- QA 中不要只凭 `ERR_ABORTED` 判断异常。
- 如果要做自动化验收，应等待页面稳定加载后再切页。

## 5. 自动化验证

后端定向测试：

```bash
python -m pytest -q backend/tests/test_energy_summary.py backend/tests/test_energy_mes_packaging_output_basis.py backend/tests/test_iot_energy_shadow.py backend/tests/test_missing_report_export_service.py backend/tests/test_attendance_process.py backend/tests/test_attendance_confirmation_service.py backend/tests/test_quality_checks.py backend/tests/test_reconciliation_flow.py backend/tests/test_realtime_routes.py
```

结果：`48 passed`

前端定向测试：

```bash
node --test tests/manageAlertsTimeline.test.js tests/manageAlertEventNormalize.test.js tests/manageAlertsPage.test.js tests/manageAlertsDesign.test.js tests/energyCenterDesign.test.js tests/attendanceOverviewDesign.test.js tests/attendanceConfirmDesign.test.js tests/workshopEnergyLiveRegression.test.js
```

结果：`60 passed`

## 6. 当前理解边界

- 本轮没有执行写入型接口，例如考勤自动处理、质量问题确认、对账问题处理。
- 本轮修改了异常页前端参数名：质量和对账接口使用 `business_date`，不再误用 `target_date`。
- 本轮没有跑后端全量测试，只跑了与异常、能耗、考勤、缺报导出相关的定向测试。
- 本轮发现的参数错接问题已修复，并补了前端测试覆盖。

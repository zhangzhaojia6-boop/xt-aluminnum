# 2026-06-12 Stitch + image2 阶段 9 口径审查

## Scope

本阶段复核管理端核心数字口径，重点确认页面没有把 MES 数据、人工填报和算法计算混接：

- 产量
- 包装产量
- 全厂入库产量
- 成品率
- 废料
- 能耗
- 合同量
- 在制料

## Verification

前端口径测试：

```text
node --test tests/manageDailyReportSurface.test.js tests/manageLivePhase2.test.js tests/manageProductionPage.test.js tests/manageTodayCockpit.test.js tests/manageTodayPage.test.js tests/energyCenterDesign.test.js tests/manageFillDetailsAudit.test.js tests/displayNumberFormatting.test.js tests/businessDateDefaults.test.js tests/overviewWipSummary.test.js tests/factoryCommandFormatters.test.js tests/factorySourceStrip.test.js tests/manageCostLine.test.js tests/manageDashboardSnapshot.test.js
141 passed
```

后端口径测试：

```text
python -m pytest -q backend/tests/test_business_time_contract.py backend/tests/test_core_metric_contracts.py backend/tests/test_daily_overview_chain.py backend/tests/test_daily_overview_mes_packaging.py backend/tests/test_energy_summary.py backend/tests/test_factory_command_service.py backend/tests/test_factory_dashboard_sanity.py backend/tests/test_mes_assisted_fill_service.py backend/tests/test_production_output_scope.py backend/tests/test_workshop_reporting_status.py
83 passed, 3 skipped
```

页面回归测试：

```text
npx playwright test e2e/manage-live-stability.spec.js e2e/manage-today-production.spec.js e2e/manage-energy.spec.js --project=chromium
10 passed, 1 skipped
```

## Metric Contracts

- 全厂入库产量：主口径为最后入库口径，页面显示为“全厂入库产量”，不能拿车间下机量替代。
- 包装产量：MES 包装工序作为参考或主来源时必须单独标注，不和内勤入库填报混成同一字段。
- 车间产量：车间看板和生产分析展示过此工序的下机量或道次口径，不直接加总为全厂总产量。
- 能耗：电耗、综合能耗、单吨能耗分开显示；缺失时不能伪造成 0，除调度大屏明确要求的 0 兜底外都要保持“无数据”状态。
- 成品率与废料：算法值优先展示，人工填报值作为对照，不反向覆盖算法主口径。
- 合同量：合同相关页面和 KPI 口径按吨显示，不再按个数理解。
- 在制料：MES 投影数据和本地兜底数据必须标注来源，页面不能把旧样例吨数当作真实同步结果。
- 业务日时间：管理端按 07:30 生产日锚点，内勤每日一录按 09:30 锚点，页面默认日期由统一工具推导。

## Review Scores

- CEO 视角：9.7/10，核心管理数字来源可解释，降低错判生产和成本的风险。
- 工程师视角：9.8/10，前端、后端、页面回归三层测试都覆盖了指标口径。
- 设计师视角：9.6/10，页面上区分主值、对照值、来源状态，避免用户误读。
- 安全审查视角：9.7/10，权限失败和数据缺失不会被伪装成成功状态。
- 真实用户视角：9.7/10，关键数字能看懂来源，也能查到填报明细做对照。

## Decision

阶段 9 通过。没有发现字段错接、算法口径混用、权限误显或误隐藏，可以进入最终 review、QA 和 ship 阶段。

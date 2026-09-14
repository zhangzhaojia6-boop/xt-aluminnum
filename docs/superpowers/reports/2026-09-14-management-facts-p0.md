# 管理总览事实显示 P0 实施记录

入口：[复盘与分阶段方案](./2026-09-14-period-dashboard-agent-design-review.md) · [封档方向](../../README.md)

用户已授权按 TDD 执行第一批修复。基线为 `78bfc56f`。本记录列出本地实施与验证；GitHub CI、合并、生产发布另以实际运行结果为准。

## 本批行为

- 趋势接口保留请求期间的每一天；没有产量证据返回 null，不省略日期。仅有燃气记录不再代表用电为零；明确记录的零用电仍保留零。
- 大图保留缺失点，缺失不进入日均；部分日期有数时标为“已知日均”。全零产量仍显示图形。缺分母不计算吨耗。
- 迷你图在数据不完整时不绘制，避免把缺失点画成下降；完整日期的大图继续保留，供查看缺口。
- 日报与经营摘要失败时，不拿生产概览中的入库量、在制量补包装产量或车间产量。生产概览本身仍可独立访问。
- 车间条形图保留缺失与真实零的区别；改为浅色图表，显式设置图例颜色，历史成本和车间图标明选定日期；按条目数给条形图足够高度。

本批不配置更新周期，不建设缓存表，不修改 MES、业务事实或正式日报 127 字段合同。网页与 Hermes 共用取证入口仍属后续阶段。

## TDD 证据

每项先运行测试观察业务断言失败，再改相应实现并运行通过，没有批量先写所有测试。

| 行为 | 修复前实际失败 | 修复后 |
|---|---|---|
| 全部能耗缺失 | 页面显示“当日 0 · 均 0” | 显示暂无能耗数据 |
| 最近一天缺失 | 历史有数时最后一天仍显示 0 | 最后一天显示 — |
| 产量含缺失日 | 100 吨加缺失被算成日均 50 | 已知日均 100；真实全零可画图 |
| 接口失败降级 | 包装产量返回入库数 73.6 | 包装产量缺失，概览数据独立保留 |
| 日期完整性 | 空测试数据库返回空数组 | 返回两个请求日期，值为 null |
| 燃气与用电区别 | 两天返回 `[0, 0]` | 仅燃气日和零用电日返回 `[null, 0]` |
| 车间缺失排序 | 缺失和零混在一起 | 缺失保留 null 并排在已知值后 |
| 历史图表日期 | 仍显示“昨日估算成本” | 显示所选日期，桌面/手机浅色可读 |
| 吨耗分母缺失 | 返回产量 0 | 产量和吨耗均缺失 |
| KPI 迷你图 | 缺失数据仍画出一条低点曲线 | 不绘制不完整迷你图 |

## 验证结果

1. 前端相关 34 项通过：数据组合、图表转换、AI 启动与聊天状态等。
2. 后端相关 30 项通过：`test_dashboard_timeseries_facts.py`、`test_daily_overview_chain.py`。新增后端测试使用实际 SQLite 测试库及正式报表服务，不替换内部计算函数。
3. 构建产物上运行 13 项浏览器测试全部通过，包含本批 5 项新测试及既有 8 项管理端测试。API 响应在浏览器外部接口处模拟；这些结果不等于生产数据验收。
4. `npm run build` 通过，仍有既有大包提示；`npm run audit` 为 0 漏洞。
5. 全量 Node 前端测试：本批 752 通过、11 失败；独立 worktree 的基线版本为 750 通过、11 失败。失败名称集合完全一致，没有本批新增失败。因此不能宣称全量前端测试通过。

11 项既有失败分布在 `frontendSecondPassPlan`（1）、`manageSettingsDrawer`（1）、`manageShellHud`（6）、`manageTodayPage`（3），涉及旧视觉标记、同步组件导入及旧布局断言。本批未改这些旧布局以迎合测试。

开发服务器上曾有 3 项动态抽屉/导航测试未通过；改用实际构建产物复核后 13 项全部通过，交付证据采用构建产物结果。

## 复现命令

在 backend 目录：

```powershell
python -m pytest tests/test_dashboard_timeseries_facts.py tests/test_daily_overview_chain.py -q --disable-warnings
```

在 frontend 目录：

```powershell
node --test tests/manageEnergyTrend.test.js tests/manageCostLine.test.js tests/manageWorkshopBarChart.test.js tests/manageDashboardSnapshot.test.js tests/manageTodayCockpit.test.js tests/assistantLauncher.test.js tests/aiChatStore.test.js
npx playwright test --config playwright.management.config.js
npm run audit
```

管理端浏览器配置会构建并启动本地预览，不需要业务后台或真实账号；测试通过登录界面使用模拟认证与 API。若已有预览，可用 `DASHBOARD_URL` 指定地址。该配置禁用 Service Worker 以隔离 API 模拟，正常用户缓存升级需另做生产验证。

## 回滚与下一步

本批没有数据库迁移，发布可回到此前合并版本 `78bfc56f`，业务事实保留。若新版本检查失败，先回退本批并保留错误证据，不修改原始数值让检查通过。

P0 通过真实页面验证后，再评估按日预计算。当天更新频率仍须明确；每 15 分钟只是上一轮讨论假设。智能体吞错回声与共同取证入口尚未在本批修复，不用本批图表测试替代智能体验收。

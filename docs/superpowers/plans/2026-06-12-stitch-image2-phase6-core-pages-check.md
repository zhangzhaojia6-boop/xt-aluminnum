# Stitch + image2 阶段 6：第一批核心页面验收记录

日期：2026-06-12

## 覆盖页面

1. `/manage/live`
2. `/manage/today`
3. `/manage/production`

## 本阶段发现并修复的问题

问题：`frontend/e2e/review-home-redesign.spec.js` 里有一条旧浏览器断言，仍认为窄屏管理端只允许 `/manage/live` 和 `/manage/today`。但当前系统已经有明确规则：带 `?desktop=1` 时，手机或窄屏也可以强制查看核心桌面管理页。

影响：旧测试会误报 `/manage/production?desktop=1` 为错误，实际上这是当前页面和路由守卫共同支持的业务能力。

处理：只更新 E2E 断言，不改路由、不放宽权限、不改页面数据映射。

## 验证命令

```powershell
node --test tests/manageLivePhase2.test.js tests/manageLiveProcessFlow.test.js tests/manageTodayCockpit.test.js tests/manageTodayPage.test.js tests/manageProductionPage.test.js tests/manageDailyReportSurface.test.js tests/manageStitchSurfaceMapping.test.js tests/useRealtimeStream.test.js
```

结果：91 个测试全部通过。

```powershell
npx playwright test e2e/review-home-redesign.spec.js --project=chromium
```

结果：5 个浏览器测试全部通过。

```powershell
node --test tests/routerGuardRules.test.js tests/manageNavigationSkeleton.test.js tests/manageShellHud.test.js tests/manageRouteRedirects.test.js
```

结果：49 个测试全部通过。

## 数据和业务口径确认

1. `/manage/live` 保持实时快照、SSE 状态、30 秒快照兜底和 1 秒数字滚动，不引入重型光效。
2. `/manage/today` 保持昨日报表和日报结算卡片，`全厂入库产量` 与工序下机量分开。
3. `/manage/production` 保持生产分析 KPI、车间排行和来源对象，不把空值伪装成成功同步。
4. MES 数据、人工填报数据、算法数据在测试中分别有映射保护。
5. 窄屏下 `desktop=1` 是显式桌面覆盖入口，普通 compact 规则仍由路由守卫控制。

## 五视角评分

1. CEO 视角：9.6/10。三张核心管理页可以稳定显示关键经营生产信息。
2. 工程师视角：9.7/10。修复只改测试旧口径，没有碰业务路由代码，风险低。
3. 设计师视角：9.5/10。页面已走 Stitch 映射层，后续仍需逐页截图继续打磨视觉颗粒度。
4. 安全审查员视角：9.7/10。权限逻辑未放宽，`desktop=1` 行为已有单元测试覆盖。
5. 真实用户视角：9.6/10。手机或窄屏需要强制看桌面管理页时不会被错误拦截。

阶段判定：通过，可以进入第二批业务页面验收和必要修复。

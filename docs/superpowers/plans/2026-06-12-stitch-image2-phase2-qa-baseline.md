# 2026-06-12 Stitch + image2 阶段 2 浏览器 QA 基线

## 结论

阶段 2 只做浏览器基线，不修代码。当前本地生产构建能启动，核心管理端大部分页面可打开，但已经暴露 7 个需要进入后续阶段处理的问题。

## 已执行检查

### 管理端核心页面

命令：

```powershell
npx playwright test e2e/compose-smoke.spec.js e2e/manage-today-production.spec.js e2e/manage-coils.spec.js e2e/manage-energy.spec.js e2e/manage-alerts-timeline.spec.js e2e/settings-center.spec.js e2e/admin-surface.spec.js --project=chromium
```

结果：35 项中 32 项通过，3 项失败。

通过覆盖：

- 登录后进入管理端。
- `/manage/admin/settings` 可打开，旧入口能跳转到设置页。
- `/manage/live` 可打开，桌面和窄屏无明显横向溢出。
- `/manage/coils` 可打开，卷级线索页可用。
- `/manage/alerts` 可打开，异常筛选和跳转可用。
- `/manage/production` 可打开，基础生产分析内容可见。

失败问题：

1. 能耗页桌面表格字段错位。测试期望第一行“电耗”为 `1,200`，页面对应单元格显示为 `-`。
2. 能耗页手机卡片字段顺序错位。测试期望第二组标签是“电耗”，实际显示为“数据来源”。
3. 昨日报表 KPI 标题不一致。测试期望 `全厂入库产量`，页面实际显示 `MES包装产量` 和 `内勤入库填报`，说明“主口径”和“对照口径”的标题还没有统一。

### 手机填报端和车间端

命令：

```powershell
npx playwright test e2e/mobile-entry-smoke.spec.js e2e/mobile-scan-entry.spec.js e2e/dynamic-entry-layout.spec.js e2e/team-lead.spec.js --project=mobile
```

结果：17 项中 13 项通过，4 项失败。

通过覆盖：

- 手机填报首页在 375、390、414、768 宽度下没有横向溢出。
- 主操逐卷填报页面可打开。
- 质量问题字段默认收起，只有选择“有填报问题”才展开。
- 历史填报按整日记录查询，不只看当前班次。
- 逐卷填报能提交顶层字段，不再错误塞进 `data` 包。

失败问题：

1. 管理员从手机端登录后停在管理端总览，测试等待 `/entry` 的班次接口超时。这里可能是旧测试口径和当前权限跳转口径不一致，也可能需要给管理员访问 `/entry` 时更明确的入口。
2. `/entry/coil/:businessDate/:shiftId` 页面没有出现测试期望的“扫码带出”按钮，实际页面停在填报首页卡片，说明旧逐卷入口和新统一填报入口不完全一致。
3. `/entry/fill` 统一逐卷填报按钮文案是“扫随行卡兜底”，测试仍找“扫码带出”，说明页面文案、测试口径和真实使用口径需要统一。
4. `/team-lead` 旧班长入口跳到了 `/entry` 后又回到 `/login`，测试仍期望 `/team-lead`。由于业务上已经取消班长口径，这个失败应优先判断为旧测试或旧入口需要灰度清理，而不是恢复班长页面。

## 基线风险清单

- 能耗页字段错位会影响用户判断“电耗、气耗、水耗、总能耗”等成本指标。
- 日报 KPI 标题不一致会让用户误以为 MES 包装产量就是最终全厂入库产量。
- 手机扫码入口文案和测试口径不一致，会导致现场人员不知道应该点哪个按钮补录随行卡。
- 旧班长入口还被测试覆盖，说明历史入口尚未完全清理或测试尚未同步业务决定。
- 前端构建成功，但包体中 `vendor-wc`、`vendor-ui`、`vendor-echarts` 较大，后续重构不能加入重型动效库。

## 阶段 2 验收

- 本阶段未修改业务代码。
- 已形成浏览器 QA 基线。
- 阻塞问题已经进入后续阶段的红灯测试和修复清单。
- 下一阶段进入设计稿冻结与字段映射红灯测试。

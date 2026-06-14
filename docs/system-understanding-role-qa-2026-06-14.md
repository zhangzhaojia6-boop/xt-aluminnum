# 鑫泰铝业 数据中枢：角色入口与权限 QA 底图

更新时间：2026-06-14 08:36 +08:00

## 1. 这份文档解决什么问题

这份文档只记录已经验证过的“谁能进哪里、谁不能进哪里、登录是否正常”。

它的作用是防止后续排查时反复从零猜：

- 管理员登录不上，到底是密码错、网络错，还是前端跳转错。
- 主操、电工、内勤扫码后应该留在手机填报端，还是能进管理端。
- 车间主任应该看全厂页面，还是只能看本车间看板。
- 哪些验证是真跑过的，哪些还没做深度提交测试。

## 2. 已确认的线上状态

### 2.1 代码和服务

- 本地分支：`main`
- 本地提交：`3a7c43a2ade5e67ffc0a409f4d1fa8d27228afd7`
- 云端运行提交：`7b9157ec3b2e5b66df3176c659398ad4a222743a`
- 云端后端服务：`aluminum-bypass.service` 为 `active`
- 云端 Nginx：`nginx` 为 `active`

说明：云端运行提交比本地少一个文档类提交；线上代码已包含管理员密码不被初始化密码覆盖的修复。

### 2.2 管理员账号

线上只读核验结果：

- 用户名：`admin`
- 账号 ID：`70`
- 名称：`系统管理员`
- 角色：`admin`
- 启用状态：启用
- 数据范围：全厂
- 管理权限：有
- 审核权限：有
- 手机端角色：不是手机填报角色

登录验证：

- `https://xtmijd.com/api/v1/auth/login` 使用 `admin / zzj200123` 返回 200。
- 真实网页登录 `https://xtmijd.com/login` 后进入 `/manage/admin/settings`。
- 登录过程没有控制台错误，没有失败请求。

结论：当前不是“管理员密码被改了”，也不是“后端登录接口坏了”。如果现场仍登录不上，优先查浏览器缓存、代理、是否用了 `www.xtmijd.com`、旧登录态。

### 2.3 域名提醒

- 正常入口：`https://xtmijd.com`
- 不建议入口：`https://www.xtmijd.com`

原因：当前 `www.xtmijd.com` 的 HTTPS 连接会失败；现场必须用不带 `www` 的域名。

## 3. 线上角色数量

线上只读统计如下：

| 角色 | 启用 | 停用 | 说明 |
|---|---:|---:|---|
| `admin` | 1 | 0 | 管理员 |
| `machine_operator` | 47 | 2 | 主操/机台填报 |
| `energy_stat` | 16 | 2 | 电工填报 |
| `consumable_stat` | 16 | 2 | 内勤/辅材/专项填报 |
| `workshop_director` | 15 | 3 | 车间主任看板 |
| `energy_chief` | 1 | 0 | 能源负责人 |
| `storage_owner` | 1 | 0 | 成品库/入库口径 |
| `quality_owner` | 1 | 0 | 质量负责人 |
| `planning_owner` | 1 | 0 | 计划负责人 |
| `recovery_owner` | 1 | 0 | 回收负责人 |
| `overhaul_owner` | 1 | 0 | 大修负责人 |
| `shipment_outflow_owner` | 1 | 0 | 发运/外流负责人 |
| `qc` | 0 | 1 | 停用旧质检角色 |

注意：`workshop_director` 是 15 个启用，不等于 13 个活跃生产车间。这里包含更宽的管理/部门口径，比如成品库等。提车间数量时要先说明是“13 个活跃生产车间”，还是“包含部门/历史保留的更宽口径”。

## 4. 已做浏览器 QA 的角色路径

本轮浏览器 QA 是只读验证，没有提交生产数据。

### 4.1 管理员

测试入口：

- `/manage/live`
- `/manage/admin/settings`

结果：

- 页面能打开。
- 管理端导航正常。
- 管理员登录后会进入管理端配置页面。
- 控制台没有红色错误。

截图证据：

- `.gstack/qa-reports/screenshots/role-qa-admin-live-2026-06-14.png`

### 4.2 主操 / 机台填报

测试入口：

- `/entry`
- `/entry/history`
- `/manage/today`

结果：

- 访问 `/entry` 后显示手机填报页。
- 访问 `/entry/history` 后显示整日历史填报页。
- 访问管理端 `/manage/today` 会被带回 `/entry`，不允许进入管理端。
- 这是正确的权限边界：主操只做现场填报，不看管理端全厂数据。

截图证据：

- `.gstack/qa-reports/screenshots/role-qa-machine-entry-2026-06-14.png`

待优化小问题：

- 手机填报页有一个状态值显示为英文 `coil_entry`，后续应映射成中文。

### 4.3 电工

测试入口：

- `/entry`
- `/entry/history`
- `/manage/today`

结果：

- 访问 `/entry` 后显示电工能耗填报。
- 访问 `/entry/history` 后显示历史填报。
- 访问管理端会被带回 `/entry`。
- 这是正确的权限边界：电工只填能耗，不进入管理端。

### 4.4 生产内勤 / 辅材填报

测试入口：

- `/entry`
- `/entry/history`
- `/manage/today`

结果：

- 访问 `/entry` 后显示内勤每日一录。
- 页面能显示 09:30 业务日归属。
- 访问管理端会被带回 `/entry`。
- 这是正确的权限边界：内勤只做补录/专项填报，不直接进管理端。

### 4.5 车间主任

测试入口：

- `/manage/workshop-dashboard`
- `/manage/today`
- `/entry/history`

结果：

- 访问 `/manage/workshop-dashboard` 后显示车间看板。
- 访问 `/manage/today` 会被带回 `/manage/workshop-dashboard`。
- 访问手机填报历史 `/entry/history` 也会被带回车间看板。
- 这是正确的权限边界：车间主任只看自己车间，不看全厂管理端，也不进入手机填报页。

截图证据：

- `.gstack/qa-reports/screenshots/role-qa-workshop-director-2026-06-14.png`

## 5. 请求失败与噪声判断

浏览器 QA 中看到过少量 `net::ERR_ABORTED`。

这类现象通常是页面切换、资源取消、SSE 长连接中断造成的“导航噪声”，不等于业务接口失败。

已经看到的例子：

- `/api/v1/mes/supplement-readiness?limit=100` 被切页中断。
- 部分前端资源在切换页面时被取消。

当前判断：

- 没有控制台红色错误。
- 没有 404/500 业务阻塞。
- 先记录为非阻塞 QA 噪声。

后续如果要做更深验证，应该区分：

- 真实业务接口返回 4xx/5xx。
- 页面切换导致旧请求被浏览器主动取消。

## 6. 当前还没完成的验证

这些不能说已经完成：

- 没有对所有 47 个主操账号逐个验证。
- 没有对所有 16 个电工、16 个内勤、15 个车间主任逐个验证。
- 没有在生产环境提交真实填报数据。
- 没有跑完所有管理端按钮级深度 QA。
- 没有完整验证钉钉、AI、多模态 agent 的真实业务闭环。
- 没有重建完整 `.understand-anything/knowledge-graph.json`，因为 `understand` 技能要求先确认 `.understandignore`。

## 7. 后续建议

下一步建议按这个顺序继续：

1. 先确认 `.understand-anything/.understandignore` 是否按当前范围执行全量 understand 图谱。
2. 继续做管理端核心页面逐页 QA：实时调度、昨日报表、生产分析、卷级线索、填报明细、能耗、异常、设置。
3. 做手机端“只读流程 + 测试库提交流程”两套验证，避免误写生产数据。
4. 把每一轮验证结果继续写入 `docs/system-understanding-*.md` 和长期记忆。


# 鑫泰铝业 数据中枢：用户权限、主数据与入口链路理解记录

日期：2026-06-14

## 结论摘要

本轮理解范围是管理端账号、权限范围、系统设置、主数据配置、车间主任看板和手机填报入口之间的关系。

当前系统不是所有账号都能进入所有页面：

- 管理员 `admin` 负责管理端配置、账号、主数据、规则和全局看板。
- `workshop_director` 是车间主任管理查看角色，只能看本车间相关看板，不是手机填报角色。
- 主操、电工、内勤/专项等移动角色通过 `/entry` 进入手机填报端。
- 管理员访问 `/entry` 会被前端带回管理端，这是设计内的权限隔离，不是手机入口坏了。

线上只读验证显示：管理员账号能正常登录，设置、账号、主数据、车间看板页面能打开；管理员访问手机入口会自动回到 `/manage/admin/settings`。本地测试库已补充验证：非管理员账号不能直接调用主数据新增、编辑、删除接口。

## 前端入口和导航

前端路由入口在 `frontend/src/router/index.js`，权限判断集中在 `frontend/src/router/guardRules.js`。

管理端核心路径：

- `/manage/admin/settings`：系统设置入口，包含主数据、别名、机列、二维码、PC 工艺映射、规则、权限和工具入口。
- `/manage/admin/users`：用户账号治理。
- `/manage/master`：车间主数据配置。
- `/manage/workshop-dashboard`：各车间看板。
- `/manage/live`、`/manage/today`、`/manage/production`：实时调度、日报、生产分析。

手机端核心路径：

- `/entry`：手机填报首页。
- `/entry/fill`：统一填报页。
- `/entry/coil`：逐卷录入工作台。
- `/entry/history`：历史填报记录。

前端导航配置在 `frontend/src/config/manage-navigation.js`：

- 普通管理员能看到管理端完整导航。
- 车间主任只显示“本车间 / 各车间看板”。
- 手机填报角色尝试进入管理端会被带回 `/entry`。

## 后端权限边界

后端角色范围集中在 `backend/app/core/scope.py` 和 `backend/app/core/permissions.py`。

关键规则：

- `build_scope_summary()` 会把用户分为管理员、全局管理者、车间主任、手机填报用户等范围。
- `workshop_director` 归入管理查看范围，且范围限制为自己的车间。
- `get_current_mobile_user()` 只允许手机填报角色访问 `/api/v1/mobile/*` 写入和读取接口。
- 管理员虽然 `entry_surface=true`，但不是移动填报用户，所以直接访问手机 API 会返回 403。

这意味着“管理员不能代替手机账号填报”是当前后端权限设计，不是前端单独限制。

## 账号和主数据现状

线上只读接口验证没有修改生产数据。抽查结果如下：

- 启用账号总数：102 个。
- 全部账号数：112 个。
- 手机端/专项相关账号：93 个。
- 机列或对象绑定账号：110 个。
- `workshop_director` 账号：18 个。
- `machine_operator` 主操账号：49 个。
- `energy_stat` 电工账号：18 个。
- `consumable_stat` 内勤/辅材账号：18 个。

车间主数据当前返回 15 个更宽口径：

- 铸锭分厂、铸轧二、铸轧三、热轧。
- 2050冷轧、1850冷轧、1650冷轧。
- 精整车间、剪切车间、拉矫车间。
- 回收车间、成品库。
- 新厂在线退火、园区在线退火、淬火车间。

这里的 `15` 是数据库/管理/专项的更宽口径，不等于“13 个活跃生产车间”。13 个活跃生产车间口径需要排除回收车间和成品库。

## 主数据和设置页面

线上 `/manage/admin/settings` 能正常打开，并展示：

- 十三车间主数据标准。
- 别名映射。
- 车间机列归一。
- 机列台账。
- 二维码与账号。
- PC 工艺映射。
- 终端绑定。
- 规则配置。
- 用户管理、组织架构、权限治理。
- QR 打印、标签服务、AI 助手、智能决策。

设置页显示当前有 `21` 个 PC 终端待建映射，接口 `mes_terminal_bindings` 返回 `0` 条绑定记录。这说明“PC 到具体机列/工艺”的映射入口已经存在，但线上真实绑定数据还没有建立好。

## 手机入口行为

线上浏览器只读验证：

- 管理员登录后访问 `/entry`，最终回到 `/manage/admin/settings`。
- 管理员登录后访问 `/entry/history`，最终也回到 `/manage/admin/settings`。
- 这是前端路由守卫和后端移动用户权限共同作用的结果。

换句话说，测试手机填报流程不能用 `admin` 账号，必须使用主操、电工、内勤或专项角色账号。

## 车间主任看板行为

线上 `/manage/workshop-dashboard` 能打开，页面包含：

- 车间切换。
- 机列填报明细。
- 电工填报明细。
- 外部 MES 明细。
- MES 对照异常。
- 在制料明细。
- 异常事务。
- 缺报追踪。

管理员全局打开时能看到更宽车间筛选；车间主任实际登录时，后端会按自己的 `workshop_id` 限制可见范围。

## 已验证结果

### 线上只读页面烟测

使用真实浏览器登录线上管理端，结果：

- `/manage/admin/settings`：正常打开。
- `/manage/admin/users`：正常打开，显示账号清单。
- `/manage/master`：正常打开，显示 15 条车间记录。
- `/manage/workshop-dashboard`：正常打开。
- `/entry`：管理员被带回管理设置页。
- `/entry/history`：管理员被带回管理设置页。

烟测过程中没有发现页面白屏。一次 `net::ERR_ABORTED` 出现在切换页面时旧请求被中止，属于导航过程噪声，不等同于业务接口失败。

### 后端定向测试

本轮运行了用户、鉴权、主数据、机列身份、车间主任、移动端和权限范围相关后端测试：

- 结果：168 passed。
- 警告：2 个 `datetime.utcnow()` 弃用提示，不影响本轮权限链路判断。

### 前端测试

本轮运行前端测试：

- 结果：665 passed。

覆盖内容包括前端路由守卫、管理端重定向、导航骨架、设置页、用户页、主数据页、车间看板、手机入口、历史记录、扫码/逐卷入口、提交保护和网络错误中文提示等。

## 风险和待处理项

1. `workshop_director` 账号数为 18，而车间主数据更宽口径为 15，活跃生产车间为 13。这里可能包含历史账号、重复账号或专项口径账号，清理前必须先导出清单确认。
2. `mes_terminal_bindings` 线上为空，但设置页提示存在 PC 终端待映射。后续要让 MES 记录稳定匹配到机列，需要先补齐 PC 到机列/工艺的绑定。
3. 管理端主数据页面显示 15 个更宽车间；生产看板、日报、分析页如果只需要生产口径，必须显式使用 13 个活跃生产车间清单，不能混用。
4. 管理员不是手机填报用户，所以本轮线上手机入口只验证了“管理员被拦截和重定向正确”，没有替代真实手机账号逐角色提交测试。
5. 旧入口和旧重定向仍有兼容价值，例如旧二维码、旧收藏链接或历史路径可能依赖它们；清理前必须先做依赖追踪。
6. 主数据写接口兜底权限风险已修复：车间、班组、员工、班次、别名映射的新增/编辑/停用接口现在都要求管理员，非管理员直接调接口会返回 `403`。

## 小白版理解

可以把系统理解成三类门：

- 管理员门：进后台，管账号、车间、机台、规则和看板。
- 车间主任门：只看自己车间的看板。
- 手机填报门：主操、电工、内勤等现场角色用来填数据。

这三类门不能随便互相串门。管理员能管系统，但不能直接冒充主操或电工填报；车间主任能看本车间，但不应该看到别的车间；手机填报人员只能填自己岗位相关数据。

## 下一步建议

- 导出 `workshop_director`、主操、电工、内勤账号和车间绑定清单，确认 18 个车间主任账号是否都还在业务中使用。
- 补齐 PC 终端到机列/工艺的绑定，让 MES 的 `PC` 设备名能稳定落到真实机列。
- 用真实主操、电工、内勤、车间主任账号各做一轮手机和看板 QA，补齐管理员无法覆盖的角色验证。
- 后续改主数据、用户或权限时，继续跑主数据写接口非管理员 `403` 测试，避免权限兜底被改坏。

## 追加复核：2026-06-14

本次继续核对管理端设置、用户管理、主数据、别名映射、PC 工艺映射的代码链路：

- 系统设置页是入口集合，不直接承载所有配置保存逻辑。
- 用户管理页调用 `/api/v1/users/*`，后端写操作已要求管理员。
- 主数据页、别名页、PC 工艺映射页调用 `/api/v1/master/*`。
- PC 工艺映射和机列账号类写接口已要求管理员。
- 车间、班组、员工、班次、别名映射写接口已补管理员兜底，这是本轮权限链路已闭环项。

本轮本地验证：

- 后端：`python -m pytest -q backend/tests/test_users_routes.py backend/tests/test_master_pagination.py backend/tests/test_workshop_template_admin_routes.py backend/tests/test_rule_configs_router.py`，结果 `16 passed`。
- 前端：`npm test --prefix frontend -- --run frontend/tests/routerGuardRules.test.js frontend/tests/manageRouteRedirects.test.js frontend/tests/manageNavigationSkeleton.test.js frontend/tests/manageSettingsDrawer.test.js frontend/tests/userManagementDesign.test.js`，实际触发当前前端测试集，结果 `666 passed`。

边界说明：这些测试能证明现有用户管理、路由守卫、设置入口和部分主数据行为没有明显回归。本轮新增的 `backend/tests/test_master_write_permissions.py` 进一步证明：非管理员直接调用主数据写接口会被后端拒绝。

## 权限修复闭环：2026-06-14

本轮用 TDD 方式补了一个小而关键的后端门锁：

- 红灯：新增测试后，旧代码下非管理员调用 `POST /api/v1/master/workshops` 会返回 `201`，说明风险真实存在。
- 修复：给车间、班组、员工、班次、别名映射的新增、编辑、删除接口统一补 `_require_admin(current_user)`。
- 绿灯：`python -m pytest -q backend/tests/test_master_write_permissions.py` 返回 `1 passed`。
- 回归：`python -m pytest -q backend/tests/test_master_write_permissions.py backend/tests/test_users_routes.py backend/tests/test_master_pagination.py backend/tests/test_workshop_template_admin_routes.py backend/tests/test_rule_configs_router.py backend/tests/test_real_master_data.py` 返回 `34 passed`。
- 前端：`npm test --prefix frontend -- --run frontend/tests/manageRouteRedirects.test.js frontend/tests/manageNavigationSkeleton.test.js frontend/tests/manageSettingsDrawer.test.js frontend/tests/userManagementDesign.test.js frontend/tests/masterWorkshopDesign.test.js frontend/tests/aliasMappingDesign.test.js` 实际触发当前前端测试集，返回 `666 passed`。

通俗理解：以前“主数据写入门”只看你有没有登录；现在会再问一句“你是不是管理员”。这样即使普通管理查看账号拿到登录令牌，也不能绕过页面直接改车间、员工、班次或别名。

# 鑫泰铝业 数据中枢：管理端登录、权限与主数据配置链路理解

日期：2026-06-14

本轮目标是只读理解管理端登录、权限、用户配置、系统设置、别名映射和车间主任边界。没有修改生产数据，没有重置密码，没有调用任何生产写接口。

## 1. 一句话结论

管理端管理员账号当前可用，`admin / zzj200123` 在线上登录接口验证成功。前端管理端入口和导航权限分层比较清楚：管理员能看系统配置和账号，车间主任只看本车间看板，主操/电工/内勤主要走手机填报端。

但后端主数据接口存在一个需要后续修复的权限风险：`/api/v1/users/*` 已经强制管理员；而 `/api/v1/master/workshops`、`/api/v1/master/teams`、`/api/v1/master/employees`、`/api/v1/master/shift-configs`、`/api/v1/master/aliases` 的部分写操作在路由层只要求登录，没有逐个调用管理员校验。前端虽然把这些页面藏在管理员入口里，但后端接口最好也补上管理员校验。

## 2. 登录链路

后端登录入口是 `POST /api/v1/auth/login`，代码在 `backend/app/routers/auth.py`。

关键规则：

- 登录会先按用户名查询 `users` 表。
- 如果是初始化管理员用户名，并且密码等于环境里的初始化管理员密码，系统会补建管理员。
- 如果用户名是初始化管理员，登录成功后会调用 `apply_admin_account_contract`，把这个账号修正成管理员身份。
- 成功登录会更新 `last_login`，并返回访问令牌、刷新令牌、用户信息和机台绑定信息。

证据位置：

- `backend/app/routers/auth.py:22` 到 `backend/app/routers/auth.py:90`
- `backend/app/services/bootstrap.py:119` 到 `backend/app/services/bootstrap.py:132`
- `backend/app/models/system.py:13` 到 `backend/app/models/system.py:32`

线上只读验证：

- `POST https://xtmijd.com/api/v1/auth/login` 使用 `admin / zzj200123` 返回 `200`
- `GET https://xtmijd.com/api/v1/auth/me` 返回管理员身份
- `GET https://xtmijd.com/login` 返回 `200`
- `GET https://xtmijd.com/manage/admin/settings` 返回 `200`

补充说明：

- `https://www.xtmijd.com/login` 当前 HTTPS 连接失败，容易被浏览器显示成 network error。
- 正确访问地址是 `https://xtmijd.com/login`，不要加 `www`。

## 3. 前端管理端路由

管理端主路由在 `frontend/src/router/index.js`。

核心入口：

| 页面 | 路由 | 角色定位 |
| --- | --- | --- |
| 实时调度墙 | `/manage/live` | 管理查看 |
| 昨日报表 | `/manage/today` | 管理查看 |
| 生产分析 | `/manage/production` | 管理查看 |
| 卷级线索 | `/manage/coils` | 管理查看 |
| 填报明细 | `/manage/fill-details` | 管理查看人工填报 |
| 能耗中心 | `/manage/energy` | 管理查看 |
| 异常处理 | `/manage/alerts` | 管理查看 |
| 各车间看板 | `/manage/workshop-dashboard` | 车间主任和管理查看 |
| 基础资料 | `/manage/master` | 管理员配置 |
| 别名映射 | `/manage/alias` | 管理员配置 |
| PC 工艺映射 | `/manage/mes-terminal-bindings` | 管理员配置 |
| 系统设置 | `/manage/admin/settings` | 管理员配置 |
| 用户管理 | `/manage/admin/users` | 管理员配置 |
| 权限治理 | `/manage/admin/governance` | 管理员配置 |
| QR 打印 | `/manage/admin/qr-print` | 管理员配置 |

旧入口兼容：

- `/admin`、`/admin/setting`、`/setting`、`/settings` 都会跳转到 `/manage/admin/settings`
- `/review/*`、`/dashboard/*`、`/master/*` 中很多旧地址会跳到新的 `/manage/*` 页面
- 这些旧路由不能随便删，必须先查二维码、历史入口和用户收藏链接

证据位置：

- `frontend/src/router/index.js:114` 到 `frontend/src/router/index.js:160`
- `frontend/src/router/index.js:180` 到 `frontend/src/router/index.js:242`

## 4. 前端权限守卫

前端权限判断主要在 `frontend/src/router/guardRules.js` 和 `frontend/src/stores/auth.js`。

通俗解释：

- 管理员：可以进入系统设置、用户管理、规则配置等管理员页面。
- 车间主任：前端会把他限制到 `/manage/workshop-dashboard`。
- 主操、电工、内勤：如果只有填报权限，会被带回 `/entry` 手机填报端。
- 管理员或管理查看角色进入 `/entry` 时，默认会被带回管理端，避免误进填报端。

证据位置：

- `frontend/src/router/guardRules.js:116` 到 `frontend/src/router/guardRules.js:143`
- `frontend/src/stores/auth.js:69` 到 `frontend/src/stores/auth.js:131`
- `frontend/src/config/manage-navigation.js:12` 到 `frontend/src/config/manage-navigation.js:86`

## 5. 后端权限边界

### 5.1 用户管理接口

用户管理接口在 `backend/app/routers/users.py`，后端有明确管理员校验。

已确认管理员校验的位置：

- 列表：`list_users` 调用 `_require_admin`
- 新增：`create_user` 调用 `_require_admin`
- 修改：`update_user` 调用 `_require_admin`
- 停用：`deactivate_user` 调用 `_require_admin`
- 重置密码：`reset_user_password` 调用 `_require_admin`

证据位置：

- `backend/app/routers/users.py:29` 到 `backend/app/routers/users.py:31`
- `backend/app/routers/users.py:265` 到 `backend/app/routers/users.py:322`
- `backend/app/routers/users.py:467` 到 `backend/app/routers/users.py:535`
- `backend/app/routers/users.py:631` 到 `backend/app/routers/users.py:690`

结论：用户管理这块后端权限比较稳。

### 5.2 车间主任看板权限

后端管理看板权限在 `backend/app/core/permissions.py`。

关键规则：

- 车间主任必须有 `workshop_id`
- 如果请求指定了别的车间，后端拒绝
- 管理员或全局范围账号可以看全厂

证据位置：

- `backend/app/core/permissions.py:105` 到 `backend/app/core/permissions.py:124`

结论：车间主任看板后端有范围校验。

### 5.3 主数据接口风险

主数据接口在 `backend/app/routers/master.py`。

已确认风险：

- `create_workshop`、`update_workshop`、`delete_workshop` 只依赖 `get_current_user`，没有调用 `_require_admin`
- `create_team`、`update_team`、`delete_team` 只依赖 `get_current_user`，没有调用 `_require_admin`
- `create_employee`、`update_employee`、`delete_employee` 只依赖 `get_current_user`，没有调用 `_require_admin`
- `create_shift_config`、`update_shift_config`、`delete_shift_config` 只依赖 `get_current_user`，没有调用 `_require_admin`
- `create_alias`、`update_alias`、`delete_alias` 只依赖 `get_current_user`，服务层也没有额外权限判断

相对安全的主数据接口：

- `create_mes_terminal_binding`、`update_mes_terminal_binding`、`delete_mes_terminal_binding` 已调用 `_require_admin`
- `update_equipment`、`create_equipment_with_account`、`reset_equipment_pin`、`toggle_equipment_status` 已调用 `_require_admin`
- 模板中心接口已停用，返回 `410 Gone`

证据位置：

- `backend/app/routers/master.py:95` 到 `backend/app/routers/master.py:154`
- `backend/app/routers/master.py:178` 到 `backend/app/routers/master.py:217`
- `backend/app/routers/master.py:329` 到 `backend/app/routers/master.py:389`
- `backend/app/routers/master.py:410` 到 `backend/app/routers/master.py:474`
- `backend/app/routers/master.py:629` 到 `backend/app/routers/master.py:684`
- `backend/app/services/master_service.py:45` 到 `backend/app/services/master_service.py:118`

业务影响：

如果某个非管理员账号拿到有效登录令牌，并且直接调用这些主数据写接口，理论上可能改动车间、班组、员工、班次或别名映射。前端页面不会暴露这些入口，但后端不应该只依赖前端隐藏按钮。

建议后续修复：

- 给主数据写接口统一补 `_require_admin(current_user)`
- 保留读接口给管理查看角色或登录用户，避免影响页面筛选
- 补后端测试：非管理员调用主数据写接口应返回 `403`
- 先在测试库验证，不直接碰生产数据

## 6. 数据表映射

| 功能 | 后端模型/表 | 说明 |
| --- | --- | --- |
| 用户账号 | `users` | 登录、角色、车间归属、手机端权限、管理员权限 |
| 系统配置 | `system_configs` | 系统级配置项 |
| 审计日志 | `audit_logs` | 登录、用户变更、主数据变更等记录 |
| 车间 | `workshops` | 车间编码、名称、类型、是否启用 |
| 班组 | `teams` | 按车间分组 |
| 员工 | `employees` | 员工、车间、班组、钉钉信息 |
| 机台 | `equipment` | 机台二维码、绑定账号、车间、班次模式 |
| PC 工艺映射 | `mes_terminal_bindings` | MES 一体机/PC 与机台、工艺的映射 |
| 别名映射 | `master_code_aliases` | 外部名称到标准编码的映射 |

证据位置：

- `backend/app/models/system.py:13` 到 `backend/app/models/system.py:78`
- `backend/app/models/master.py:12` 到 `backend/app/models/master.py:161`

## 7. 前端 API 映射

| 前端页面 | 前端 API 文件 | 后端接口 |
| --- | --- | --- |
| 登录页 | `frontend/src/api/auth.js` | `/api/v1/auth/login`、`/api/v1/auth/me` |
| 用户管理 | `frontend/src/api/users.js` | `/api/v1/users/*` |
| 基础资料 | `frontend/src/api/master.js` | `/api/v1/master/workshops`、`/teams`、`/employees`、`/equipment`、`/shift-configs` |
| 别名映射 | `frontend/src/api/master.js` | `/api/v1/master/aliases` |
| PC 工艺映射 | `frontend/src/api/master.js` | `/api/v1/master/mes-terminal-bindings` |
| 系统设置 | `SystemSettingsPage.vue` | 页面入口为主，同时读取 MES 辅助就绪度 |

证据位置：

- `frontend/src/api/auth.js`
- `frontend/src/api/users.js`
- `frontend/src/api/master.js`
- `frontend/src/views/master/UserManagement.vue`
- `frontend/src/views/master/AliasMapping.vue`
- `frontend/src/views/manage/admin/SystemSettingsPage.vue`

## 8. 本轮验证记录

线上只读验证：

- `POST /api/v1/auth/login`：`200`
- `GET /api/v1/auth/me`：`200`
- `GET /api/v1/users/?limit=5`：`200`
- `GET /api/v1/master/workshops?limit=30`：`200`
- `GET /api/v1/master/aliases?limit=5`：`200`
- `GET /api/v1/master/mes-terminal-bindings?limit=5`：`200`
- `GET /api/v1/master/equipment?limit=5`：`200`
- `GET /api/v1/master/shift-configs?limit=5`：`200`
- `GET /login`、`/manage/admin/settings`、`/manage/admin/users`、`/manage/alias`、`/manage/master`、`/manage/workshop-dashboard`：页面返回 `200`

本地测试：

- `npm test --prefix frontend -- --run frontend/tests/routerGuardRules.test.js frontend/tests/manageNavigationSkeleton.test.js frontend/tests/manageSettingsDrawer.test.js frontend/tests/manageRouteRedirects.test.js`
- 实际执行结果：当前前端测试集 `665 passed`
- `python -m pytest backend/tests/test_auth_routes.py -q`
- 实际执行结果：`12 passed`

边界说明：

- 本轮没有跑全量后端 pytest。
- 本轮没有用非管理员真实账号在线调用生产写接口，因为这会造成生产数据风险。
- 本轮没有做全站浏览器逐按钮点击，只做了页面可达和接口只读验证。

## 9. 当前优先级建议

高优先级：

1. 补主数据写接口后端管理员校验。
2. 给主数据写接口增加非管理员 `403` 测试。
3. 把 `www.xtmijd.com` 的访问问题处理掉，或者在用户侧统一只给 `xtmijd.com` 无 `www` 地址。

中优先级：

1. 系统设置页现在更像入口集合，需要继续把“配置项真实读写来源”拆清楚。
2. 用户管理页可以保留当前真实角色，但建议后续加“最近使用/最后填报/最后登录”辅助清理冗余账号。
3. 别名映射页可以增加“影响范围预览”，让用户知道改一个别名会影响哪些 MES 映射、日报或看板。

可后续处理：

1. 旧路由兼容入口很多，后续可以按访问日志灰度清理。
2. 系统配置表 `system_configs` 当前更多用于基础配置，部分配置仍来自环境变量，需要继续梳理。


# 鑫泰铝业 数据中枢：主数据接口权限审计

日期：2026-06-14

本轮目标是继续理解系统，重点审计“基础资料 / 主数据 / 别名映射 / 用户管理”的前后端权限是否一致。全程只用本地临时库复现风险，没有调用生产写接口，没有修改生产数据。

## 1. 核心结论

前端入口是收住的：普通观察角色、车间主任、手机填报角色不会在导航里看到主数据配置入口；车间主任导航只给本车间看板。

后端用户管理接口也是收住的：`/api/v1/users/*` 的列表、新增、修改、停用、重置密码都要求管理员。

真正风险集中在 `backend/app/routers/master.py`：部分主数据写接口只要求“已登录”，没有要求“管理员”。这意味着如果非管理员拿到有效登录态，并绕过前端直接请求接口，可能改动车间、班组、员工、班次和别名映射。

## 2. 权限模型通俗解释

可以把系统想成两道门：

- 第一道门是前端页面：普通用户看不到“系统设置”“基础资料”“别名映射”等入口。
- 第二道门是后端接口：即使别人不走页面、直接调用接口，也应该被后端挡住。

当前情况是：

- 用户管理有两道门。
- 机台配置和 PC 工艺映射有两道门。
- 车间、班组、员工、班次、别名映射前端有门，后端部分写接口少了一道管理员门。

## 3. 自动扫描出的主数据接口清单

脚本扫描 `backend/app/routers/master.py` 得到以下结果。

| 接口 | 函数 | 写操作 | 当前后端权限 | 风险 |
| --- | --- | --- | --- | --- |
| `GET /master/yield-rate-deprecation-map` | `get_yield_rate_deprecation_map` | 否 | 管理查看 | 无 |
| `GET /master/process-business-map` | `get_process_business_map` | 否 | 管理查看 | 无 |
| `GET /master/workshops` | `list_workshops` | 否 | 已登录 | 可接受 |
| `POST /master/workshops` | `create_workshop` | 是 | 已登录 | 高 |
| `PUT /master/workshops/{workshop_id}` | `update_workshop` | 是 | 已登录 | 高 |
| `DELETE /master/workshops/{workshop_id}` | `delete_workshop` | 是 | 已登录 | 高 |
| `GET /master/aliases` | `list_aliases` | 否 | 已登录 | 可接受或中 |
| `POST /master/aliases` | `create_alias` | 是 | 已登录 | 高 |
| `PUT /master/aliases/{alias_id}` | `update_alias` | 是 | 已登录 | 高 |
| `DELETE /master/aliases/{alias_id}` | `delete_alias` | 是 | 已登录 | 高 |
| `GET /master/mes-terminal-bindings` | `list_mes_terminal_bindings` | 否 | 已登录 | 可接受或中 |
| `POST /master/mes-terminal-bindings` | `create_mes_terminal_binding` | 是 | 管理员 | 无 |
| `PUT /master/mes-terminal-bindings/{binding_id}` | `update_mes_terminal_binding` | 是 | 管理员 | 无 |
| `DELETE /master/mes-terminal-bindings/{binding_id}` | `delete_mes_terminal_binding` | 是 | 管理员 | 无 |
| `GET /master/workshop-templates/{template_key}` | `get_workshop_template_detail` | 否 | 管理员，且返回停用 | 无 |
| `PUT /master/workshop-templates/{template_key}` | `upsert_workshop_template` | 是 | 管理员，且返回停用 | 无 |
| `GET /master/teams` | `list_teams` | 否 | 已登录 | 可接受 |
| `POST /master/teams` | `create_team` | 是 | 已登录 | 高 |
| `PUT /master/teams/{team_id}` | `update_team` | 是 | 已登录 | 高 |
| `DELETE /master/teams/{team_id}` | `delete_team` | 是 | 已登录 | 高 |
| `GET /master/employees` | `list_employees` | 否 | 已登录 | 可接受或中 |
| `POST /master/employees` | `create_employee` | 是 | 已登录 | 高 |
| `PUT /master/employees/{employee_id}` | `update_employee` | 是 | 已登录 | 高 |
| `DELETE /master/employees/{employee_id}` | `delete_employee` | 是 | 已登录 | 高 |
| `GET /master/equipment` | `list_equipment` | 否 | 已登录 | 可接受 |
| `GET /master/equipment/{equipment_id}` | `get_equipment_detail` | 否 | 已登录 | 可接受 |
| `PATCH /master/equipment/{equipment_id}` | `update_equipment` | 是 | 管理员 | 无 |
| `POST /master/equipment/create-with-account` | `create_equipment_with_account` | 是 | 管理员 | 无 |
| `POST /master/equipment/{equipment_id}/reset-pin` | `reset_equipment_pin` | 是 | 管理员 | 无 |
| `POST /master/equipment/{equipment_id}/toggle-status` | `toggle_equipment_status` | 是 | 管理员 | 无 |
| `GET /master/shift-configs` | `list_shift_configs` | 否 | 已登录 | 可接受 |
| `GET /master/shifts` | `list_shifts_compat` | 否 | 已登录 | 可接受 |
| `POST /master/shift-configs` | `create_shift_config` | 是 | 已登录 | 高 |
| `PUT /master/shift-configs/{shift_config_id}` | `update_shift_config` | 是 | 已登录 | 高 |
| `DELETE /master/shift-configs/{shift_config_id}` | `delete_shift_config` | 是 | 已登录 | 高 |

## 4. 本地临时库复现结果

复现方法：

- 使用本地内存 SQLite 临时库。
- 伪造一个非管理员用户：`role=machine_operator`。
- 直接请求主数据写接口。
- 不使用生产数据库，不调用线上写接口。

复现结果：

| 操作 | 结果 |
| --- | --- |
| 非管理员 `PUT /api/v1/master/workshops/1` | `200`，可以修改车间 |
| 非管理员 `PUT /api/v1/master/teams/1` | `200`，可以修改班组 |
| 非管理员 `PUT /api/v1/master/employees/1` | `200`，可以修改员工 |
| 非管理员 `PUT /api/v1/master/shift-configs/1` | `200`，可以修改班次 |
| 非管理员 `PUT /api/v1/master/aliases/1` | `200`，可以修改别名 |
| 非管理员 `PATCH /api/v1/master/equipment/1` | `403`，正确拒绝 |

这个对照说明：不是鉴权系统整体失效，而是 `master.py` 部分写接口缺少管理员校验。

## 5. 前端侧验证

前端相关测试通过：

```text
node --test tests/manageNavigationSkeleton.test.js tests/manageSettingsDrawer.test.js tests/workshopMasterDesign.test.js tests/userManagementDesign.test.js tests/aliasMapping.test.js

结果：22 passed
```

测试覆盖的含义：

- 车间主任导航只看到自己的车间看板。
- 管理员能看到系统设置、用户管理、主数据配置入口。
- 普通观察角色看不到管理员配置项。
- 主数据页面仍然保留真实 CRUD 前端能力。

所以前端没有把入口乱暴露出来；风险是后端接口层应该再补一把锁。

## 6. 涉及代码和表

后端路由：

- `backend/app/routers/master.py`
- `backend/app/routers/users.py`
- `backend/app/core/permissions.py`

前端入口：

- `frontend/src/router/index.js`
- `frontend/src/config/manage-navigation.js`
- `frontend/src/config/manage-settings-drawer.js`
- `frontend/src/views/master/Workshop.vue`
- `frontend/src/views/master/AliasMapping.vue`
- `frontend/src/views/master/UserManagement.vue`

涉及表：

- `workshops`
- `teams`
- `employees`
- `shift_configs`
- `master_code_aliases`
- `equipment`
- `mes_terminal_bindings`
- `users`
- `audit_logs`

## 7. 业务影响

高风险影响：

- 车间名称或启停状态被误改，会影响日报、看板、筛选、机台归属。
- 班组或班次被误改，会影响填报时间、班次统计、缺报判断。
- 员工被误改，会影响后续钉钉、考勤、责任人映射。
- 别名映射被误改，会影响 MES 外部数据归一，导致卷材、车间、机台匹配错。

为什么还没有立刻造成明显事故：

- 前端入口已隐藏，普通用户正常点页面看不到这些操作。
- 需要拿到有效登录态并直接调用接口才会触发。
- 机台和 PC 工艺映射这类更敏感操作已经有管理员校验。

但从安全设计看，后端不能只相信前端隐藏按钮，所以仍应修复。

## 8. 建议修复方案

建议下一步按 TDD 修复：

1. 先写失败测试：非管理员调用主数据写接口应全部返回 `403`。
2. 给以下函数补 `_require_admin(current_user)`：
   - `create_workshop`
   - `update_workshop`
   - `delete_workshop`
   - `create_alias`
   - `update_alias`
   - `delete_alias`
   - `create_team`
   - `update_team`
   - `delete_team`
   - `create_employee`
   - `update_employee`
   - `delete_employee`
   - `create_shift_config`
   - `update_shift_config`
   - `delete_shift_config`
3. 保留读接口现状，避免影响页面筛选和填报端基础信息读取。
4. 补管理员正向测试，确认管理员仍可维护这些基础资料。
5. 本地测试通过后再部署。

回滚方案：

- 如果补权限后发现某个真实业务角色确实需要写主数据，应新增一个明确权限角色，而不是回退到“所有登录用户都能写”。
- 代码回滚只需要回退 `backend/app/routers/master.py` 和对应测试文件。

## 9. 当前结论

当前系统管理端页面权限基本清楚，用户管理和车间主任边界比较稳。主数据接口存在后端权限收口缺口，建议作为下一轮高优先级修复项处理。


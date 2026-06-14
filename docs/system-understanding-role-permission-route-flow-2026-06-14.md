# 鑫泰铝业 数据中枢：角色权限与页面流向理解记录

日期：2026-06-14

本记录只描述当前代码和本轮验证结果。没有重置密码，没有修改线上生产数据，也没有调用生产写接口。

## 1. 一句话结论

系统现在是“两道门”：

1. 前端先把用户带到合适页面，避免普通填报人员误进管理端。
2. 后端接口再按角色、车间、班组、班次检查一次，真正决定能不能读写数据。

所以，前端隐藏按钮只是用户体验，后端权限才是安全边界。

## 2. 登录为什么看起来像“密码变了”

当前线上主域名 `https://xtmijd.com` 的管理端登录接口可用，管理员账号登录接口返回成功。

容易误判的点是：`https://www.xtmijd.com` 当前连接失败。用户如果从带 `www` 的地址打开登录页，浏览器或前端会更像是显示“网络错误”，而不是“账号或密码不正确”。

建议对外只发这个地址：

```text
https://xtmijd.com/login
```

后续可以把 `www.xtmijd.com` 统一跳转到 `xtmijd.com`，这样现场人员不会因为输错域名而以为密码变了。

## 3. 管理员密码不会被启动流程自动覆盖

当前代码已经有保护：

- 已存在的 `admin` 用户，不会因为环境变量里的初始化密码变化而被自动改密码。
- 只有显式传入 `--reset-password` 的管理员脚本，或者管理员在用户管理页面执行“重置密码”，才会改已有账号密码。

证据：

- `backend/app/routers/auth.py`：登录时校验数据库里的 `password_hash`。
- `backend/scripts/create_admin.py`：默认只修正管理员身份合同，不重置密码；只有 `reset_password=True` 才重置。
- `scripts/reset_admin.py`：必须显式提供 `ADMIN_NEW_PASSWORD`，拒绝硬编码密码。
- `backend/tests/test_admin_bootstrap.py`：覆盖“已有 admin 保留原密码”和“显式 reset 才重置”。

## 4. 主要角色怎么走页面

| 角色 | 主要入口 | 能看到什么 | 不能看到什么 |
| --- | --- | --- | --- |
| 管理员 `admin` | `/manage/admin/settings` | 系统配置、用户、主数据、管理看板 | 默认不进入手机填报端 |
| 车间主任 `workshop_director` | `/manage/workshop-dashboard` | 自己车间看板 | 全厂大屏、其他车间数据、管理员配置 |
| 主操 `machine_operator` | `/entry` | 手机填报、历史填报、扫码填报 | 管理端页面 |
| 电工 `energy_stat` | `/entry` | 电工填报字段 | 管理端页面 |
| 辅材/内勤类 `consumable_stat` 等 | `/entry` | 对应补录或专项字段 | 管理端页面 |
| 统计/审核/经理类 | `/manage/today` 等 | 管理查看页，按自身范围过滤 | 管理员配置页 |

通俗理解：

- 管理员是“系统管家”。
- 车间主任是“只看自己车间的主管”。
- 主操、电工、内勤是“现场填报人员”。
- 统计/审核/经理是“看报表的人”。

## 5. 前端权限流向

前端主要看三个文件：

- `frontend/src/stores/auth.js`
- `frontend/src/router/guardRules.js`
- `frontend/src/config/navigation.js`

前端登录后会把后端返回的用户信息整理成几个“入口能力”：

- `adminSurface`：能不能进管理员配置。
- `reviewSurface`：能不能进管理查看页。
- `entrySurface`：能不能进手机填报端。
- `isWorkshopDirector`：是不是车间主任。
- `isFillOnlyRole`：是不是只能填报、不能看管理端。

前端路由守卫的核心规则：

- 只有填报权限的人访问管理端，会被带回 `/entry`。
- 管理/审核角色进入 `/entry`，会被带回管理端，避免误进手机端。
- 车间主任进入管理端非车间看板页面，会被带回 `/manage/workshop-dashboard`。
- 手机上访问管理端时，审核角色只允许进入少数核心管理页；车间主任仍只留在车间看板。

## 6. 后端权限兜底

后端主要看三个文件：

- `backend/app/core/deps.py`
- `backend/app/core/scope.py`
- `backend/app/core/permissions.py`

后端权限流向：

1. `get_current_user` 先校验令牌，只允许激活用户。
2. `build_scope_summary` 根据用户角色算出数据范围。
3. `assert_mobile_user_access` 限制手机填报接口。
4. `assert_reviewer_access` 限制审核/查看接口。
5. `assert_manager_dashboard_access` 限制车间主任看板范围。
6. `assert_manage_override_access` 限制管理员级覆盖操作。

车间主任的关键规则：

- 必须绑定 `workshop_id`。
- 只能看自己的 `workshop_id`。
- 请求其他车间会被后端拒绝。
- 全厂日报、全厂生产分析等全局页面会拒绝车间主任。

## 7. 用户管理的权限

用户管理接口在 `backend/app/routers/users.py`。

已确认这些接口都要求管理员：

- 用户列表
- 用户详情
- 新增用户
- 修改用户
- 停用用户
- 重置密码
- 钉钉通讯录同步

这意味着普通车间主任、主操、电工、内勤不能直接通过用户接口改账号或重置密码。

## 8. 已验证测试

本轮定向测试：

```text
python -m pytest -q backend/tests/test_admin_bootstrap.py backend/tests/test_auth_routes.py backend/tests/test_workshop_director_scope.py backend/tests/test_dashboard_routes.py::test_global_dashboard_routes_reject_workshop_director
```

结果：

```text
20 passed
```

前端测试：

```text
npm test --prefix frontend -- --run frontend/tests/routerGuardRules.test.js
```

实际执行结果：

```text
665 passed
```

说明：前端脚本当前会跑完整 `frontend/tests/*.test.js`，所以这次不是只跑一个路由守卫文件，而是跑了前端整套 node 测试。

## 9. 已知风险和后续建议

### 高优先级

1. 给 `www.xtmijd.com` 配置跳转或证书，否则用户容易误进错误域名并看到网络错误。
2. 检查所有主数据写接口是否都已经在后端强制管理员权限，不能只靠前端隐藏入口。
3. 把“登录失败原因”在前端显示得更明确：密码错、账号停用、网络连不上应分开提示。

### 中优先级

1. `frontend/src/stores/auth.js` 读取 `super_admin_surface`，但当前 `UserInfo` schema 没有稳定返回这个字段；如果以后要让管理员切换到填报端，需要补齐后端字段或删掉这条前端分支。
2. `workshopQuickEntry` 前端仍保留入口函数，但后端当前没有对应路由；删除或恢复前必须先查历史二维码和旧入口依赖。
3. 多角色真实浏览器 QA 仍需要有效角色账号或只读二维码登录方式，不能只靠管理员账号证明所有角色都可用。

## 10. 下次排查顺序

如果再次出现“管理端登不上”：

1. 先确认地址是不是 `https://xtmijd.com/login`，不要带 `www`。
2. 再确认浏览器是否开了代理、缓存了旧页面或旧登录态。
3. 如果后端返回 400，才按“账号或密码不正确”排查。
4. 如果后端返回 403，按“账号被停用”排查。
5. 如果请求没有到后端，按网络、代理、域名、证书排查。
6. 不要第一步就重置密码，避免把简单域名问题变成账号管理问题。

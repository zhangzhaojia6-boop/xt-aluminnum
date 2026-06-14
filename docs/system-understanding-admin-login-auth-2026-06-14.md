# 鑫泰铝业 数据中枢：管理端登录链路理解记录

日期：2026-06-14

## 结论

管理端 `admin` 账号的线上密码本次没有被改坏。线上只读验证显示：

- `/api/v1/auth/login` 返回 200。
- `/api/v1/auth/me` 返回 200。
- 真实浏览器从 `/login` 登录后落到 `/manage/admin/settings`。
- 登录返回用户角色为 `admin`，`admin_surface=true`。

因此，用户侧看到“连接服务器失败”时，不应优先判断为密码变了；更可能是浏览器代理、缓存、旧登录态、Service Worker 缓存或本机网络拦截导致请求没有正常到后端。

## 当前登录链路

### 前端

- 登录页：`frontend/src/views/Login.vue`
- 登录接口封装：`frontend/src/api/auth.js`
- 通用接口错误文案：`frontend/src/api/index.js`
- 登录状态存储：`frontend/src/stores/auth.js`

前端登录页使用 `/api/v1/auth/login`。如果后端明确返回 400 或 401，页面显示“账号或密码不正确”；如果没有拿到后端响应，才会通过通用错误文案显示“连接服务器失败，请检查网络、代理或稍后重试”。

### 后端

- 登录路由：`backend/app/routers/auth.py`
- 用户模型：`backend/app/models/system.py`
- 管理员账号初始化与修复：`backend/app/services/bootstrap.py`
- 密码哈希工具：`backend/app/core/auth.py`

后端登录流程是：

1. 按 `username` 查询 `users` 表。
2. 使用 `verify_password` 校验输入密码和 `password_hash`。
3. `admin` 账号登录成功后，只修正管理员账号合同字段，不再用初始化密码覆盖已有密码。
4. 如果账号停用，返回 403。
5. 成功后写入 `last_login`，返回 access token、refresh token 和用户信息。

## 已修复过的历史风险

提交 `7b9157e fix: prevent init admin password from overriding existing admin` 已移除旧逻辑：

- 旧逻辑：如果已有 `admin` 用初始化密码登录失败，可能把已有管理员密码重置为初始化密码。
- 当前逻辑：已有 `admin` 必须通过当前数据库里的 `password_hash` 校验；初始化密码只用于首次创建不存在的管理员。

这条修复可以防止部署或配置变化把已有管理员密码意外覆盖。

## 线上只读验证结果

本次验证没有修改生产数据，只进行了登录请求和页面打开：

- API 登录状态：200。
- `/auth/me` 状态：200。
- 浏览器最终路径：`/manage/admin/settings`。
- 登录用户角色：`admin`。
- 管理端权限：已开启。

出于安全原因，文档不保存明文密码。

## 下次排查顺序

如果再次出现“管理端登不上”：

1. 先确认用户名是否填写 `admin`，不要填“系统管理员”。
2. 如果页面提示“账号或密码不正确”，再查密码哈希或账号是否被改。
3. 如果页面提示“连接服务器失败”，先查代理、浏览器缓存、旧 Token、Service Worker、公司网络拦截。
4. 用无痕窗口打开 `https://xtmijd.com/login` 复测。
5. 再用只读接口验证 `/api/v1/auth/login` 和 `/api/v1/auth/me`。
6. 不要因为看到 `network error` 就直接重置密码。

## QA 边界

本次只验证了管理端登录链路，不代表全站所有按钮和所有角色都完成深度 QA。长期系统理解目标仍需继续覆盖更多页面、接口、数据库表和外部服务。

## 追加复核：域名和 network error 边界

时间：2026-06-14 13:40

本轮又做了一次线上只读健康探测：

- `https://xtmijd.com/api/v1/healthz`：HTTP 200。
- `https://xtmijd.com/api/v1/readyz`：HTTP 200，`status=ready`。
- `https://xtmijd.com/healthz`：HTTP 200。
- `https://xtmijd.com/readyz`：HTTP 200，`status=ready`。
- `https://www.xtmijd.com/api/v1/healthz`：连接失败。

因此，如果用户说“登录显示 network error”或“连接服务器失败”，第一优先级不是重置密码，而是确认：

1. 地址必须是 `https://xtmijd.com/login`，不要带 `www`。
2. 关闭代理或换无痕窗口重试。
3. 清理旧缓存和旧登录态。
4. 如果页面能返回“账号或密码不正确”，说明请求已经到后端；如果仍是“连接服务器失败”，说明浏览器到服务器这条路还没通。

本轮还确认了前端错误文案逻辑：`frontend/src/api/index.js` 会把真正没有后端响应的错误翻译成“连接服务器失败，请检查网络、代理或稍后重试”。这条提示是网络/域名/代理方向，不等同于密码错误。

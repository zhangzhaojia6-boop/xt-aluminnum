# API System Lane Spec

## Identity Boundary

`/api/v1/auth/*`、`/api/v1/dingtalk/*` 统一用户/设备/钉钉 H5 / 浏览器进入系统。

- `backend/app/routers/dingtalk.py`：钉钉 H5 身份入口。
- `backend/app/adapters/wecom/group_bot.py`：workflow publisher 的企业微信群机器人。
- 企业微信用户登录路径已下线。
- 企业微信群机器人不属于身份入口。

| Lane | Files |
| --- | --- |
| User / Session | `auth.py`、`dingtalk.py`、`users.py` |

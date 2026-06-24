# API System Lane Spec

## 身份边界

`/api/v1/auth/*`、`/api/v1/dingtalk/*` 是当前身份相关入口。统一用户/设备/钉钉 H5 / 浏览器进入系统。

- `backend/app/routers/dingtalk.py`：钉钉 H5 身份入口。
- `backend/app/adapters/wecom/group_bot.py`：workflow publisher 的企业微信群机器人。
- 企业微信用户登录路径已下线。
- 企业微信群机器人不属于身份入口。

## Lane

| Lane | 文件 | 说明 |
| --- | --- | --- |
| User / Session | `auth.py`、`dingtalk.py`、`users.py` | 登录、会话、用户管理、钉钉身份绑定 |
| Agent / Hermes | `agent.py`、`rag.py` | 智能体、知识库、数据追溯 |
| Report | `reports.py`、`report_service` | 日报、看板、发布工作流 |

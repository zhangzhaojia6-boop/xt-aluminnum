# Codex 施工指令 — Phase 1B: 企业微信集成 + 极简工人前端

> **前置条件**：Phase 1A 全部完成且测试通过。
> **约束**：严格按照本文档执行，不允许自行增加功能或修改架构。

---

## 目标

1. 实现企业微信自建 H5 应用的身份认证（OAuth2 免密登录）
2. 创建极简工人填报页面（一屏完成，大字大按钮）
3. 实现企业微信应用消息推送（催报、日报、异常）
4. 工人通过企业微信打开应用 → 自动登录 → 填报 → 提交 → 自动确认 → 领导看到

---

## 任务 1: 企业微信 API 适配器

### 文件：`backend/app/adapters/wecom.py`

```python
"""
企业微信 API 适配器。
封装所有与企业微信服务器的交互，包括：
- access_token 获取与缓存
- OAuth2 授权码换取 userid
- 应用消息推送
- JS-SDK 签名
"""
from __future__ import annotations
import hashlib
import time
import logging
from datetime import datetime, timedelta

import httpx

from app.config import settings

logger = logging.getLogger('wecom')

# access_token 缓存（内存级别，生产环境应用 Redis）
_token_cache: dict[str, tuple[str, datetime]] = {}
_jsapi_ticket_cache: dict[str, tuple[str, datetime]] = {}

WECOM_API_BASE = 'https://qyapi.weixin.qq.com/cgi-bin'


async def get_access_token() -> str:
    """
    获取企业微信 access_token。
    有效期 7200 秒，提前 300 秒刷新。
    """
    cache_key = f'{settings.WECOM_CORP_ID}:{settings.WECOM_AGENT_ID}'
    if cache_key in _token_cache:
        token, expires_at = _token_cache[cache_key]
        if datetime.utcnow() < expires_at:
            return token

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f'{WECOM_API_BASE}/gettoken',
            params={
                'corpid': settings.WECOM_CORP_ID,
                'corpsecret': settings.WECOM_APP_SECRET,
            },
        )
        data = resp.json()
        if data.get('errcode', 0) != 0:
            raise RuntimeError(f'企业微信 access_token 获取失败: {data}')

        token = data['access_token']
        expires_in = data.get('expires_in', 7200)
        _token_cache[cache_key] = (token, datetime.utcnow() + timedelta(seconds=expires_in - 300))
        return token


async def code_to_userid(code: str) -> str:
    """
    通过 OAuth2 授权码获取企业微信 userid。

    参数：
        code: 前端通过 wx.config 获取的授权码

    返回：
        企业微信的 userid 字符串
    """
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f'{WECOM_API_BASE}/auth/getuserinfo',
            params={'access_token': token, 'code': code},
        )
        data = resp.json()
        if data.get('errcode', 0) != 0:
            raise RuntimeError(f'企业微信用户身份获取失败: {data}')
        userid = data.get('userid') or data.get('UserId')
        if not userid:
            raise RuntimeError(f'企业微信返回数据中无 userid: {data}')
        return userid


async def send_app_message(userid: str, content: str, *, msg_type: str = 'text') -> dict:
    """
    通过企业微信应用消息推送文本消息给指定用户。

    参数：
        userid: 企业微信用户ID，多个用 | 分隔
        content: 消息内容
        msg_type: 消息类型，默认 text

    返回：
        企业微信 API 响应
    """
    token = await get_access_token()
    payload = {
        'touser': userid,
        'msgtype': msg_type,
        'agentid': int(settings.WECOM_AGENT_ID),
        'text': {'content': content},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f'{WECOM_API_BASE}/message/send',
            params={'access_token': token},
            json=payload,
        )
        data = resp.json()
        if data.get('errcode', 0) != 0:
            logger.error('消息推送失败: %s', data)
        return data


async def get_jsapi_ticket() -> str:
    """获取 JS-SDK ticket，用于前端 wx.config 签名。"""
    cache_key = 'jsapi_ticket'
    if cache_key in _jsapi_ticket_cache:
        ticket, expires_at = _jsapi_ticket_cache[cache_key]
        if datetime.utcnow() < expires_at:
            return ticket

    token = await get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f'{WECOM_API_BASE}/get_jsapi_ticket',
            params={'access_token': token},
        )
        data = resp.json()
        if data.get('errcode', 0) != 0:
            raise RuntimeError(f'JS-SDK ticket 获取失败: {data}')

        ticket = data['ticket']
        expires_in = data.get('expires_in', 7200)
        _jsapi_ticket_cache[cache_key] = (ticket, datetime.utcnow() + timedelta(seconds=expires_in - 300))
        return ticket


def generate_jsapi_signature(url: str, *, ticket: str, noncestr: str, timestamp: int) -> str:
    """
    生成 JS-SDK 签名。

    签名算法：sha1(jsapi_ticket=xxx&noncestr=xxx&timestamp=xxx&url=xxx)
    """
    sign_str = f'jsapi_ticket={ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}'
    return hashlib.sha1(sign_str.encode()).hexdigest()
```

---

## 任务 2: 企业微信认证路由

### 文件：`backend/app/routers/wecom.py`

```python
"""
企业微信回调与认证路由。
处理 OAuth2 登录、JS-SDK 签名、消息回调。
"""
from __future__ import annotations
import time
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import create_access_token
from app.database import get_db
from app.models.system import User

router = APIRouter(tags=['wecom'])


class WecomLoginRequest(BaseModel):
    code: str  # 企业微信 OAuth2 授权码


class WecomLoginResponse(BaseModel):
    token: str
    user_id: int
    display_name: str


class JsapiSignatureRequest(BaseModel):
    url: str  # 当前页面 URL（不含 # 后面的部分）


class JsapiSignatureResponse(BaseModel):
    app_id: str
    timestamp: int
    nonce_str: str
    signature: str


@router.post('/login', response_model=WecomLoginResponse)
async def wecom_login(req: WecomLoginRequest, db: Session = Depends(get_db)):
    """
    企业微信 OAuth2 登录。

    流程：
    1. 用 code 换取 userid
    2. 通过 userid 在 users 表中查找对应用户（匹配 username 或 wecom_userid 字段）
    3. 找到则签发 JWT token
    4. 找不到则返回 403

    注意：
    - 如果 WECOM_APP_ENABLED 为 false，返回 503
    - userid 匹配逻辑：先查 User.username == userid，如果没有再查 User 的其他字段
    """
    if not settings.WECOM_APP_ENABLED:
        raise HTTPException(status_code=503, detail='企业微信应用未启用')

    from app.adapters.wecom import code_to_userid
    try:
        wecom_userid = await code_to_userid(req.code)
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # 查找对应的系统用户
    user = db.query(User).filter(User.username == wecom_userid).first()
    if not user:
        # 尝试其他匹配方式（后续可扩展）
        raise HTTPException(status_code=403, detail=f'企业微信用户 {wecom_userid} 未在系统中注册')

    if not user.is_active:
        raise HTTPException(status_code=403, detail='账号已停用')

    token = create_access_token(user.id)
    return WecomLoginResponse(
        token=token,
        user_id=user.id,
        display_name=user.name or user.username,
    )


@router.post('/jsapi-signature', response_model=JsapiSignatureResponse)
async def get_jsapi_signature(req: JsapiSignatureRequest):
    """
    获取 JS-SDK 签名，用于前端 wx.config。

    注意：如果 WECOM_APP_ENABLED 为 false，返回 503
    """
    if not settings.WECOM_APP_ENABLED:
        raise HTTPException(status_code=503, detail='企业微信应用未启用')

    from app.adapters.wecom import get_jsapi_ticket, generate_jsapi_signature

    ticket = await get_jsapi_ticket()
    timestamp = int(time.time())
    nonce_str = secrets.token_hex(8)
    signature = generate_jsapi_signature(
        req.url,
        ticket=ticket,
        noncestr=nonce_str,
        timestamp=timestamp,
    )

    return JsapiSignatureResponse(
        app_id=settings.WECOM_CORP_ID or '',
        timestamp=timestamp,
        nonce_str=nonce_str,
        signature=signature,
    )
```

### 修改文件：`backend/app/main.py`

在路由注册区域添加：
```python
from app.routers import wecom
app.include_router(wecom.router, prefix=f'{settings.API_V1_PREFIX}/wecom')
```

---

## 任务 3: 极简工人填报页面

### 文件：`frontend/src/views/WorkerForm.vue`

设计原则（必须严格遵守）：
- **一屏完成**：所有字段在一屏内，不需要滚动
- **大字大按钮**：字体最小 18px，按钮高度 56px，圆角 12px
- **零思考**：不需要工人选择车间/班次/日期，系统自动识别
- **中文**：所有文字纯中文，无英文、无技术术语
- **配色简单**：白色背景 + 蓝色主按钮 + 红色错误提示
- **无导航**：不需要侧边栏/顶栏/底部导航，就是一个填报页面

```vue
<template>
  <div class="worker-form">
    <!-- 顶部信息（系统自动填充，工人只看不填） -->
    <div class="worker-form__header">
      <div class="worker-form__info">
        <span class="worker-form__label">{{ shiftInfo }}</span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="worker-form__loading">
      正在加载...
    </div>

    <!-- 错误状态 -->
    <div v-else-if="loadError" class="worker-form__error">
      <p>{{ loadError }}</p>
      <button class="worker-form__btn" @click="load">重试</button>
    </div>

    <!-- 已提交状态 -->
    <div v-else-if="submitted" class="worker-form__success">
      <div class="worker-form__check">✓</div>
      <p class="worker-form__success-text">提交成功</p>
      <button class="worker-form__btn worker-form__btn--secondary" @click="reset">继续填报</button>
    </div>

    <!-- 填报表单 -->
    <div v-else class="worker-form__body">
      <!-- 退回提示（如果被Agent退回） -->
      <div v-if="returnedReason" class="worker-form__returned">
        <p><strong>请修改后重新提交：</strong></p>
        <p>{{ returnedReason }}</p>
      </div>

      <!-- 出勤人数 -->
      <div class="worker-form__field">
        <label>出勤人数</label>
        <input
          v-model.number="form.attendance_count"
          type="number"
          inputmode="numeric"
          placeholder="填写人数"
          class="worker-form__input"
        />
      </div>

      <!-- 投入重量 -->
      <div class="worker-form__field">
        <label>投入重量（吨）</label>
        <input
          v-model.number="form.input_weight"
          type="number"
          inputmode="decimal"
          step="0.001"
          placeholder="填写重量"
          class="worker-form__input"
        />
      </div>

      <!-- 产出重量 -->
      <div class="worker-form__field">
        <label>产出重量（吨）</label>
        <input
          v-model.number="form.output_weight"
          type="number"
          inputmode="decimal"
          step="0.001"
          placeholder="填写重量"
          class="worker-form__input"
        />
      </div>

      <!-- 废品重量（可选） -->
      <div class="worker-form__field">
        <label>废品重量（吨）<span class="worker-form__optional">选填</span></label>
        <input
          v-model.number="form.scrap_weight"
          type="number"
          inputmode="decimal"
          step="0.001"
          placeholder="没有可不填"
          class="worker-form__input"
        />
      </div>

      <!-- 日用电量（可选） -->
      <div class="worker-form__field">
        <label>日用电量（度）<span class="worker-form__optional">选填</span></label>
        <input
          v-model.number="form.electricity_daily"
          type="number"
          inputmode="decimal"
          placeholder="没有可不填"
          class="worker-form__input"
        />
      </div>

      <!-- 提交按钮 -->
      <button
        class="worker-form__btn worker-form__btn--primary"
        :disabled="submitting"
        @click="submit"
      >
        {{ submitting ? '提交中...' : '提交' }}
      </button>

      <!-- 保存草稿 -->
      <button
        class="worker-form__btn worker-form__btn--secondary"
        :disabled="submitting"
        @click="saveDraft"
      >
        先保存，稍后提交
      </button>
    </div>
  </div>
</template>

<!--
script setup 实现要求：

1. 页面加载时调用 /api/v1/mobile/bootstrap 获取当前班次信息
2. shiftInfo 显示格式："铸轧车间 · 早班 · 4月4日"（自动填充，工人不可编辑）
3. 如果当前有已退回的草稿（status=returned），自动加载到表单并显示退回原因
4. submit 调用现有的 /api/v1/mobile/report 接口
5. 提交成功后显示"✓ 提交成功"
6. 提交失败显示错误信息（来自 Agent 的中文反馈）
7. saveDraft 调用同一接口但传 action='save'（保存草稿）

企业微信集成：
1. 页面加载时检测是否在企业微信环境（window.__wxjs_environment === 'miniprogram' 或 navigator.userAgent 含 wxwork）
2. 如果在企业微信环境，调用 /api/v1/wecom/jsapi-signature 获取签名
3. 调用 wx.config 和 wx.agentConfig 初始化
4. 如果不在企业微信环境（开发模式），使用正常的 JWT 登录
-->

<style scoped>
.worker-form {
  max-width: 480px;
  margin: 0 auto;
  padding: 20px 16px;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.worker-form__header {
  text-align: center;
  margin-bottom: 24px;
}

.worker-form__info {
  font-size: 16px;
  color: #666;
}

.worker-form__field {
  margin-bottom: 20px;
}

.worker-form__field label {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.worker-form__optional {
  font-size: 14px;
  color: #999;
  font-weight: 400;
  margin-left: 4px;
}

.worker-form__input {
  width: 100%;
  height: 56px;
  font-size: 20px;
  border: 2px solid #ddd;
  border-radius: 12px;
  padding: 0 16px;
  box-sizing: border-box;
  -webkit-appearance: none;
  appearance: none;
}

.worker-form__input:focus {
  outline: none;
  border-color: #1677ff;
}

.worker-form__btn {
  display: block;
  width: 100%;
  height: 56px;
  font-size: 20px;
  font-weight: 600;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  margin-top: 16px;
}

.worker-form__btn--primary {
  background: #1677ff;
  color: #fff;
}

.worker-form__btn--primary:disabled {
  background: #a0c4ff;
}

.worker-form__btn--secondary {
  background: #f5f5f5;
  color: #666;
}

.worker-form__returned {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
  font-size: 16px;
  color: #cf1322;
}

.worker-form__success {
  text-align: center;
  padding: 60px 0;
}

.worker-form__check {
  font-size: 64px;
  color: #52c41a;
}

.worker-form__success-text {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-top: 16px;
}

.worker-form__loading {
  text-align: center;
  font-size: 18px;
  color: #999;
  padding: 60px 0;
}

.worker-form__error {
  text-align: center;
  font-size: 18px;
  color: #cf1322;
  padding: 40px 0;
}
</style>
```

### 修改文件：`frontend/src/router/index.js`

添加新路由（在 mobile 路由组中）：
```javascript
{
  path: '/worker',
  name: 'worker-form',
  component: () => import('../views/WorkerForm.vue'),
  meta: { requiresAuth: true, title: '生产填报', zone: 'mobile' }
},
```

---

## 任务 4: 修改 .env.example

在文件末尾添加：
```bash
# 企业微信自建应用（Phase 1B）
# 在企业微信管理后台 → 应用管理 → 自建应用中获取
# WECOM_CORP_ID=你的企业ID
# WECOM_AGENT_ID=你的应用AgentId
# WECOM_APP_SECRET=你的应用Secret
# WECOM_APP_ENABLED=true
# WORKFLOW_ENABLED=true
```

---

## 执行顺序

1. 任务 1（wecom adapter）→ 确认无 import 错误
2. 任务 2（wecom router + main.py 注册）→ 启动后端确认 /docs 中出现 wecom 路由
3. 任务 3（WorkerForm.vue + router）→ npm run dev 确认页面渲染
4. 任务 4（.env.example）

## 禁止事项

- ❌ 不要安装企业微信相关的第三方 SDK（直接用 httpx 调用 API）
- ❌ 不要修改现有的 Login.vue 或认证流程
- ❌ 不要引入 Redis 或其他缓存中间件
- ❌ 不要修改 docker-compose.yml
- ❌ 不要修改已有的 Vue 组件
- ❌ 不要在 WorkerForm.vue 中使用 Element Plus 组件（用原生 HTML，保持极简）
- ❌ 不要添加任何英文到 WorkerForm.vue 的用户可见文字中

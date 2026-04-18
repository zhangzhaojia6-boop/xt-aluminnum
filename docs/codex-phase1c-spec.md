# Codex 施工指令 — Phase 1C: 自动报告生成与推送

> **前置条件**：Phase 1A + 1B 完成且测试通过。
> **约束**：严格按照本文档执行。

---

## 目标

1. 汇总Agent 完整实现：定时汇总已确认数据，生成日报
2. 报告Agent 实现：自动发布日报 + 通过企业微信推送给领导
3. 催报Agent 升级：接入企业微信消息推送
4. 驾驶舱改为实时自动更新（去掉手动刷新）

---

## 任务 1: 完善汇总 Agent

### 修改文件：`backend/app/agents/aggregator.py`

完善 `execute` 方法的实现：

```python
def execute(self, *, db: Session, target_date: date) -> list[AgentDecision]:
    """
    实现逻辑：

    1. 查询当日所有 ShiftProductionData，按 data_status 分类统计：
       - confirmed_count: data_status='confirmed' 的记录数
       - pending_count: data_status in ('pending', 'submitted') 的记录数
       - total_expected: 当日应报班次数（查 ShiftConfig + Workshop 交叉）

    2. 如果 confirmed_count == 0，记录 warning 并返回（不生成空报告）

    3. 计算汇总数据：
       - 各车间总产量（output_weight 求和）
       - 各车间总投入（input_weight 求和）
       - 各车间成材率（output_weight / input_weight * 100）
       - 总出勤人数（actual_headcount 求和）
       - 总能耗（electricity_kwh 求和）
       - 上报率（confirmed_count / total_expected * 100）

    4. 生成文本摘要（boss_summary），格式：
       "{日期} 生产日报：今日产量 {X} 吨，上报率 {Y}%，
        成材率 {Z}%，出勤 {N} 人。{缺失提示}"

       如果有未报班次，追加：
       "注意：{pending_count}个班次尚未提交。"

    5. 调用现有的 report_service 逻辑创建 DailyReport 记录，
       但直接设置 status='published'（跳过 draft→reviewed→published 人工链）
       设置 published_by = None（表示系统自动发布）

    6. 记录 AgentDecision（AUTO_AGGREGATE + AUTO_PUBLISH）

    注意：
    - 复用现有的 report_service.py 中的数据查询逻辑
    - 如果当日已有 published 状态的日报，不重复生成（幂等）
    - 不要 commit
    """
```

---

## 任务 2: 完善催报 Agent 并接入企业微信

### 修改文件：`backend/app/agents/reminder.py`

完善 `execute` 方法：

```python
def execute(self, *, db: Session, target_date: date, shift_config_id: int | None = None) -> list[AgentDecision]:
    """
    实现逻辑：

    1. 查询当日应该提交但未提交的班次：
       - 通过排班表或设备绑定确定"应报"列表
       - 排除已提交（status in submitted/approved/auto_confirmed）的班次

    2. 对每个未提交班次：
       a. 查找负责人（team leader 或 equipment bound user）
       b. 查询已有催报记录（MobileReminderRecord），获取催报次数
       c. 如果催报次数 < 3：
          - 创建新催报记录
          - 调用 send_reminder_message(userid, content)
       d. 如果催报次数 >= 3：
          - 升级通知管理员
          - 调用 send_escalation_message(admin_userid, content)

    3. send_reminder_message 和 send_escalation_message：
       - 如果 WECOM_APP_ENABLED=true，调用 wecom.send_app_message
       - 如果 WECOM_APP_ENABLED=false，只记录日志（不发送）

    催报消息模板：
    "【催报提醒】{车间名称} {班次名称} 的生产数据尚未提交，
     请尽快在企业微信中完成填报。（第{N}次提醒）"

    升级消息模板：
    "【催报升级】{车间名称} {班次名称} 已催报{N}次未响应，
     请管理员关注。负责人：{工人姓名}"
    """
```

---

## 任务 3: 创建报告 Agent

### 修改文件：`backend/app/agents/reporter.py`

```python
"""
报告 Agent。
替代旧流程中"发布报告"的人工操作。
在汇总Agent生成日报后，自动推送给领导。
"""
from __future__ import annotations
import asyncio
from datetime import date

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.config import settings


class ReporterAgent(BaseAgent):
    """报告Agent：自动推送日报给领导"""

    def __init__(self):
        super().__init__('reporter')

    def execute(self, *, db: Session, target_date: date) -> list[AgentDecision]:
        """
        推送日报给领导。

        流程：
        1. 查询当日 status='published' 的 DailyReport
        2. 如果没有已发布的日报，不推送
        3. 获取所有 role='admin' 或 role='manager' 的用户
        4. 对每个领导用户：
           - 如果 WECOM_APP_ENABLED=true，推送企业微信消息
           - 如果 WECOM_APP_ENABLED=false，只记录日志

        推送消息格式：
        "【生产日报】{日期}
         今日产量：{X} 吨
         上报率：{Y}%
         成材率：{Z}%
         出勤：{N} 人

         {boss_summary 中的完整文本}"

        5. 记录 AgentDecision
        """
        self._decisions = []
        # 实现逻辑
        return self._decisions


reporter_agent = ReporterAgent()
```

---

## 任务 4: 更新定时任务编排

### 修改文件：`backend/app/main.py`

更新 `lifespan` 中的定时任务，添加报告推送任务：

```python
from app.agents.reporter import reporter_agent

def _run_reporter():
    """每天定时推送日报（在汇总之后执行）"""
    with SessionLocal() as session:
        try:
            reporter_agent.execute(db=session, target_date=date_type.today())
            session.commit()
        except Exception:
            session.rollback()
            reporter_agent.logger.exception('Reporter failed')

# 报告推送：每天 7:00, 12:00, 18:00, 22:00
scheduler.add_job(_run_reporter, 'cron', hour='7,12,18,22', id='agent_reporter')
```

---

## 任务 5: 驾驶舱去掉手动刷新

### 修改文件：`frontend/src/views/dashboard/FactoryDirector.vue`

1. 删除"刷新"按钮（`<el-button @click="load">刷新</el-button>`）
2. 将 `setInterval(load, 60000)` 改为 `setInterval(load, 30000)`（30秒自动刷新）
3. 合并"老板摘要"和"老板最终版文本日报"为一个卡片：
   - 如果 `data.final_text_summary` 有值，显示最终版
   - 否则显示 `data.boss_summary`
   - 卡片标题改为"今日报告"
4. 删除最后一个卡片（老板最终版文本日报那个独立卡片）

---

## 执行顺序

1. 任务 1（汇总Agent）→ 添加测试验证汇总逻辑
2. 任务 2（催报Agent）→ 确认消息模板正确
3. 任务 3（报告Agent）→ 确认推送逻辑
4. 任务 4（定时任务）→ 启动后端确认无报错
5. 任务 5（驾驶舱）→ npm run dev 确认页面渲染

## 禁止事项

- ❌ 不要修改 DailyReport 模型结构
- ❌ 不要引入新的 pip 包
- ❌ 不要修改认证流程
- ❌ 不要在推送消息中使用英文
- ❌ 不要删除驾驶舱中除"刷新按钮"和"最终版日报卡片"之外的任何元素

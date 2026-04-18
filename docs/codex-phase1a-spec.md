# Codex 施工指令 — Phase 1A: 智能体引擎基础

> **角色定义**：你是施工层，严格按照本文档执行。不允许自行增加功能、修改架构、引入未指定的依赖、或重构未提到的文件。每个任务完成后停下来等待验收。

---

## 背景与第一性原理

本项目是河南鑫泰铝业的生产数据管理系统。

**旧流程（正在消灭的）：**
```
50+工人手写/微信群报数 → 6组专业统计员人工汇总 → 综合部总统计核对 → 领导
耗时4-8小时，层层接力，重复汇总，数据滞后
```

**新流程（正在实现的）：**
```
工人手机填报 → 系统自动校验+确认 → 自动汇总+发布 → 领导驾驶舱
耗时<5分钟，零人工环节
```

**核心判断标准**：任何需要"人工点击确认/审核/发布"才能让数据从工人流向领导的设计，都是在重建旧流程，必须消灭。

当前系统的错误：建了一个 reviewer 角色和 5 步人工审核链（pending→reviewed→confirmed→published→locked），本质上是把旧流程的统计员变成了数字版审核员。

---

## 总体目标

本阶段（Phase 1A）实现：
1. 创建 Agent 框架和规则引擎
2. 改造提交流程：工人提交 → 自动校验 → 自动确认（无人工）
3. 改造报告生成：定时自动触发 → 自动发布（无人工）
4. 精简状态机和权限模型

---

## 约束规则（必须遵守）

1. **不引入新的 Python 依赖**。所有 Agent 用纯 Python 实现（不用 claude-agent-sdk，那是 Phase 2 的事）
2. **不修改数据库表结构**。通过 `data_status` 字段的新值实现新状态机，不加新列不删旧列
3. **不删除旧代码文件**。旧的 reviewer 流程暂时保留（只是不再被新流程使用），避免破坏存量功能
4. **不修改前端**。前端改动在 Phase 1B
5. **所有新代码必须有 docstring**。用中文写功能说明
6. **保持现有测试可通过**。运行 `cd backend && python -m pytest` 必须通过

---

## 任务 1: 创建规则引擎

### 文件：`backend/app/rules/__init__.py`

```python
"""
规则引擎包。
提供数据校验规则和自动确认规则，替代人工审核。
"""
```

### 文件：`backend/app/rules/validation.py`

创建数据校验规则模块。功能要求：

```python
"""
数据校验规则集。
当工人提交数据时，校验Agent调用这些规则判断数据是否合格。
合格则自动确认，不合格则退回工人并给出具体修改指引。
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """校验结果"""
    passed: bool  # 是否通过
    errors: list[str]  # 失败原因列表（中文，给工人看的）
    warnings: list[str]  # 警告（不阻止提交，但会记录）


def validate_shift_report(data: dict, *, workshop_code: str | None = None) -> ValidationResult:
    """
    校验班次报告数据。

    规则：
    1. 必填字段检查：attendance_count, input_weight, output_weight 必须有值
    2. 数值范围检查：所有重量字段 >= 0
    3. 逻辑一致性：output_weight <= input_weight（产出不能大于投入）
    4. 合理范围：attendance_count 在 1-50 之间
    5. 能耗合理性：electricity_daily >= 0（如果填了的话）
    6. gas_daily >= 0（如果填了的话）

    参数：
        data: 报告数据字典，包含 attendance_count, input_weight, output_weight,
              scrap_weight, electricity_daily, gas_daily 等字段
        workshop_code: 车间编码，用于车间特定规则（预留）

    返回：
        ValidationResult 对象
    """
    # 实现上述规则
    # errors 中的文字必须是工人能看懂的中文，例如：
    # - "请填写出勤人数"
    # - "产出重量不能大于投入重量，请检查"
    # - "出勤人数应在1到50之间"
```

### 文件：`backend/app/rules/auto_confirm.py`

```python
"""
自动确认规则。
当数据通过所有校验规则后，自动将状态设为 auto_confirmed。
替代旧流程中的人工审核确认。
"""
from __future__ import annotations
from dataclasses import dataclass
from .validation import validate_shift_report, ValidationResult


@dataclass(frozen=True)
class AutoConfirmResult:
    """自动确认结果"""
    confirmed: bool  # 是否自动确认
    validation: ValidationResult  # 校验详情
    reason: str  # 确认/拒绝原因


def evaluate_auto_confirm(data: dict, *, workshop_code: str | None = None) -> AutoConfirmResult:
    """
    评估是否自动确认。

    流程：
    1. 调用 validate_shift_report 校验
    2. 如果校验全部通过（无 errors），则 confirmed=True
    3. 如果有 errors，则 confirmed=False
    4. warnings 不阻止确认，但记录到 reason 中

    返回：
        AutoConfirmResult 对象
    """
```

### 文件：`backend/app/rules/thresholds.py`

```python
"""
阈值配置。
定义各种规则的阈值，集中管理，方便调整。
"""

# 考勤
MIN_ATTENDANCE = 1
MAX_ATTENDANCE = 50

# 重量（吨）
MIN_WEIGHT = 0.0
MAX_SINGLE_SHIFT_WEIGHT = 500.0  # 单班次最大产量

# 能耗
MIN_ENERGY = 0.0
MAX_ELECTRICITY_DAILY = 100000.0  # 度
MAX_GAS_DAILY = 50000.0  # 立方

# 差异核对
RECONCILIATION_TOLERANCE_PERCENT = 5.0  # 差异在5%以内自动确认
```

---

## 任务 2: 创建 Agent 框架

### 文件：`backend/app/agents/__init__.py`

```python
"""
智能体模块。
每个 Agent 替代旧流程中的一个人工环节。
Agent 由事件或定时器驱动，自主运行，无需人工触发。
"""
```

### 文件：`backend/app/agents/base.py`

创建 Agent 基类：

```python
"""
Agent 基类。
所有智能体继承此基类，提供统一的执行、日志、审计接口。
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentAction(str, Enum):
    """Agent 操作类型"""
    AUTO_CONFIRM = 'auto_confirm'       # 自动确认
    AUTO_REJECT = 'auto_reject'         # 自动退回
    AUTO_FLAG = 'auto_flag'             # 标记异常
    AUTO_AGGREGATE = 'auto_aggregate'   # 自动汇总
    AUTO_PUBLISH = 'auto_publish'       # 自动发布
    AUTO_REMIND = 'auto_remind'         # 自动催报
    AUTO_RECONCILE = 'auto_reconcile'   # 自动核对
    AUTO_ALERT = 'auto_alert'           # 自动预警


@dataclass
class AgentDecision:
    """Agent 决策记录"""
    agent_name: str          # 哪个 Agent
    action: AgentAction      # 做了什么
    target_type: str         # 操作对象类型（如 'mobile_shift_report'）
    target_id: int           # 操作对象 ID
    reason: str              # 决策原因
    details: dict[str, Any] = field(default_factory=dict)  # 详情
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BaseAgent(ABC):
    """
    Agent 基类。

    所有 Agent 必须实现 execute() 方法。
    基类提供：
    - 日志记录
    - 审计日志（通过 record_decision）
    - 统一的错误处理
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f'agent.{name}')
        self._decisions: list[AgentDecision] = []

    @abstractmethod
    def execute(self, **kwargs) -> list[AgentDecision]:
        """
        执行 Agent 逻辑。
        返回本次执行的所有决策记录。
        """
        ...

    def record_decision(
        self,
        action: AgentAction,
        target_type: str,
        target_id: int,
        reason: str,
        **details,
    ) -> AgentDecision:
        """记录一条决策"""
        decision = AgentDecision(
            agent_name=self.name,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            details=details,
        )
        self._decisions.append(decision)
        self.logger.info(
            '%s | %s | %s#%d | %s',
            self.name, action.value, target_type, target_id, reason,
        )
        return decision
```

### 文件：`backend/app/agents/validator.py`

```python
"""
校验 Agent。
替代旧流程中专业统计员（孙俊桃、贺晓艳等）的核对工作。

触发时机：工人提交报告时（由 mobile_report_service 调用）
输入：工人提交的报告数据
输出：自动确认 或 退回修改（附原因）
"""
from __future__ import annotations
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.rules.auto_confirm import evaluate_auto_confirm


class ValidatorAgent(BaseAgent):
    """校验Agent：数据提交后自动校验并确认/退回"""

    def __init__(self):
        super().__init__('validator')

    def execute(self, *, db: Session, report_id: int, report_data: dict, workshop_code: str | None = None) -> list[AgentDecision]:
        """
        校验并自动确认/退回一条报告。

        流程：
        1. 调用 evaluate_auto_confirm 校验数据
        2. 如果通过：
           - 更新 MobileShiftReport.status = 'auto_confirmed'
           - 更新关联的 ShiftProductionData.data_status = 'confirmed'
           - 记录决策
        3. 如果不通过：
           - 更新 MobileShiftReport.status = 'returned'
           - 设置 returned_reason 为校验失败原因（中文）
           - 记录决策
        4. 返回决策列表

        注意：
        - 必须在同一个数据库事务中完成
        - 不要 commit，让调用方控制事务
        - confirmed_by / rejected_by 设为 None（表示系统自动操作）
        - 在 notes 字段追加 "[自动校验] " 前缀
        """
        self._decisions = []
        result = evaluate_auto_confirm(report_data, workshop_code=workshop_code)

        from app.models.production import MobileShiftReport, ShiftProductionData

        report = db.query(MobileShiftReport).filter(MobileShiftReport.id == report_id).first()
        if not report:
            self.logger.warning('Report #%d not found', report_id)
            return self._decisions

        if result.confirmed:
            # 自动确认
            report.status = 'approved'  # 保持与现有前端兼容

            # 同步更新关联的 ShiftProductionData
            if report.linked_production_data_id:
                spd = db.query(ShiftProductionData).filter(
                    ShiftProductionData.id == report.linked_production_data_id
                ).first()
                if spd:
                    spd.data_status = 'confirmed'
                    spd.notes = f'[自动校验通过] {result.reason}'

            self.record_decision(
                AgentAction.AUTO_CONFIRM,
                'mobile_shift_report',
                report_id,
                result.reason,
                warnings=result.validation.warnings,
            )
        else:
            # 退回修改
            report.status = 'returned'
            report.returned_reason = '\n'.join(result.validation.errors)

            self.record_decision(
                AgentAction.AUTO_REJECT,
                'mobile_shift_report',
                report_id,
                f'校验未通过：{"; ".join(result.validation.errors)}',
                errors=result.validation.errors,
            )

        return self._decisions


# 全局单例
validator_agent = ValidatorAgent()
```

### 文件：`backend/app/agents/aggregator.py`

```python
"""
汇总 Agent。
替代旧流程中综合部总统计的"接收汇总、形成总表"工作。

触发时机：定时任务（每个班次结束后1小时），或手动触发
输入：指定日期的所有已确认班次数据
输出：自动生成日报并发布
"""
from __future__ import annotations
from datetime import date

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent


class AggregatorAgent(BaseAgent):
    """汇总Agent：自动汇总已确认数据并生成日报"""

    def __init__(self):
        super().__init__('aggregator')

    def execute(self, *, db: Session, target_date: date) -> list[AgentDecision]:
        """
        汇总指定日期的生产数据并生成日报。

        流程：
        1. 查询 target_date 所有 data_status='confirmed' 的 ShiftProductionData
        2. 按车间汇总：总产量、总投入、总能耗、成材率、出勤
        3. 调用现有的 report_service.run_daily_pipeline 生成日报
           - 但跳过 blocker 检查（confirmed_only=False 改为自动处理）
        4. 自动设置日报 status='published'（不等人工发布）
        5. 记录决策

        注意：
        - 如果没有任何已确认的数据，不生成日报（记录 warning）
        - 如果有部分班次未提交，仍然生成日报（在摘要中注明缺失班次）
        - 不要 commit
        """
        self._decisions = []
        # 实现逻辑
        return self._decisions


# 全局单例
aggregator_agent = AggregatorAgent()
```

### 文件：`backend/app/agents/reminder.py`

```python
"""
催报 Agent。
替代旧流程中"追报"的人工工作。

触发时机：定时任务（每个班次结束后30分钟）
输入：未提交报告的班次列表
输出：通过企业微信发送催报消息（Phase 1B 实现推送，本阶段只记录）
"""
from __future__ import annotations
from datetime import date

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent


class ReminderAgent(BaseAgent):
    """催报Agent：自动检测未报班次并催报"""

    def __init__(self):
        super().__init__('reminder')

    def execute(self, *, db: Session, target_date: date, shift_config_id: int | None = None) -> list[AgentDecision]:
        """
        检查未提交报告的班次并发送催报。

        流程：
        1. 查询 target_date 应该提交但未提交的班次
        2. 对每个未提交班次：
           a. 查找对应的班长/操作工
           b. 创建催报记录（MobileReminderRecord）
           c. 记录决策
        3. 如果催报次数 >= 3，升级通知管理员

        注意：
        - 复用现有的 mobile_reminder_service 逻辑
        - 本阶段不发送实际消息（Phase 1B 接入企业微信后实现）
        - 只创建记录和日志
        """
        self._decisions = []
        # 实现逻辑
        return self._decisions


# 全局单例
reminder_agent = ReminderAgent()
```

---

## 任务 3: 改造提交流程

### 修改文件：`backend/app/services/mobile_report_service.py`

在 `save_or_submit_report` 函数中，找到提交逻辑（status 从 draft 变为 submitted 的地方），在提交成功后增加自动校验调用。

**精确修改要求：**

1. 在文件顶部 import 区域添加：
```python
from app.agents.validator import validator_agent
```

2. 找到提交逻辑中设置 `report.status = 'submitted'` 或类似的地方，在该行之后、事务 commit 之前，添加：

```python
# === 自动校验（替代人工审核）===
# 工人提交后，由校验Agent自动判断数据是否合格
# 合格则自动确认，不合格则退回修改
if report.status == 'submitted':
    _report_data = {
        'attendance_count': getattr(report, 'attendance_count', None),
        'input_weight': _to_float(getattr(report, 'input_weight', None)),
        'output_weight': _to_float(getattr(report, 'output_weight', None)),
        'scrap_weight': _to_float(getattr(report, 'scrap_weight', None)),
        'electricity_daily': _to_float(getattr(report, 'electricity_daily', None)),
        'gas_daily': _to_float(getattr(report, 'gas_daily', None)),
    }
    _decisions = validator_agent.execute(
        db=db,
        report_id=report.id,
        report_data=_report_data,
        workshop_code=getattr(context_workshop, 'code', None) if 'context_workshop' in dir() else None,
    )
    # 决策已由 agent 记录到日志
```

**重要约束：**
- 不要删除或修改已有的 `save_or_submit_report` 函数签名
- 不要删除任何现有校验逻辑
- 只在 `submitted` 状态设置之后添加上述代码
- 如果找不到精确的插入位置，先通读整个函数，找到 `report.status` 被设为提交状态的代码行
- 保持现有的事务管理不变

---

## 任务 4: 注册定时任务

### 修改文件：`backend/app/main.py`

在 `lifespan` 函数中注册 Agent 定时任务。

**精确修改要求：**

1. 在 import 区域添加：
```python
from app.agents.aggregator import aggregator_agent
from app.agents.reminder import reminder_agent
```

2. 在 `lifespan` 函数中，`scheduler.start()` 之前添加：

```python
        # 注册智能体定时任务
        from app.database import SessionLocal
        from datetime import date as date_type

        def _run_aggregator():
            """每小时检查是否有需要汇总的数据"""
            with SessionLocal() as session:
                try:
                    aggregator_agent.execute(db=session, target_date=date_type.today())
                    session.commit()
                except Exception:
                    session.rollback()
                    aggregator_agent.logger.exception('Aggregator failed')

        def _run_reminder():
            """每30分钟检查未提交的班次"""
            with SessionLocal() as session:
                try:
                    reminder_agent.execute(db=session, target_date=date_type.today())
                    session.commit()
                except Exception:
                    session.rollback()
                    reminder_agent.logger.exception('Reminder failed')

        scheduler.add_job(_run_aggregator, 'interval', hours=1, id='agent_aggregator')
        scheduler.add_job(_run_reminder, 'interval', minutes=30, id='agent_reminder')
```

---

## 任务 5: 单元测试

### 文件：`backend/tests/test_rules.py`

```python
"""规则引擎单元测试"""
from app.rules.validation import validate_shift_report
from app.rules.auto_confirm import evaluate_auto_confirm


class TestValidation:
    """校验规则测试"""

    def test_valid_data_passes(self):
        """完整合法数据应通过校验"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 95.0,
            'scrap_weight': 5.0,
            'electricity_daily': 5000.0,
            'gas_daily': 1000.0,
        }
        result = validate_shift_report(data)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_missing_attendance_fails(self):
        """缺少出勤人数应失败"""
        data = {
            'input_weight': 100.0,
            'output_weight': 95.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False
        assert any('出勤' in e for e in result.errors)

    def test_output_exceeds_input_fails(self):
        """产出大于投入应失败"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 150.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False
        assert any('产出' in e or '投入' in e for e in result.errors)

    def test_negative_weight_fails(self):
        """负数重量应失败"""
        data = {
            'attendance_count': 10,
            'input_weight': -10.0,
            'output_weight': 5.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False

    def test_attendance_out_of_range_fails(self):
        """出勤人数超范围应失败"""
        data = {
            'attendance_count': 100,
            'input_weight': 100.0,
            'output_weight': 95.0,
        }
        result = validate_shift_report(data)
        assert result.passed is False


class TestAutoConfirm:
    """自动确认规则测试"""

    def test_valid_data_auto_confirms(self):
        """合法数据应自动确认"""
        data = {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 95.0,
            'scrap_weight': 5.0,
        }
        result = evaluate_auto_confirm(data)
        assert result.confirmed is True

    def test_invalid_data_not_confirmed(self):
        """不合法数据不应确认"""
        data = {
            'attendance_count': 10,
            'input_weight': 50.0,
            'output_weight': 100.0,  # 产出 > 投入
        }
        result = evaluate_auto_confirm(data)
        assert result.confirmed is False
```

---

## 执行顺序

1. **先执行任务 1**（规则引擎），运行 `cd backend && python -m pytest tests/test_rules.py` 确认通过
2. **再执行任务 2**（Agent 框架），确认无 import 错误
3. **再执行任务 3**（改造提交流程），运行全量测试确认无回归
4. **再执行任务 4**（注册定时任务），确认服务启动无报错
5. **最后执行任务 5**（补充测试），全量测试通过

## 禁止事项

- ❌ 不要修改 `backend/app/models/` 中的任何模型定义
- ❌ 不要修改 `frontend/` 中的任何文件
- ❌ 不要修改 `docker-compose.yml`
- ❌ 不要修改 `requirements.txt`
- ❌ 不要创建新的 alembic migration
- ❌ 不要引入任何新的 pip 包
- ❌ 不要修改现有的 API 路由
- ❌ 不要删除任何现有函数
- ❌ 不要添加 print 语句，用 logging
- ❌ 不要修改 `.env` 或 `.env.example`

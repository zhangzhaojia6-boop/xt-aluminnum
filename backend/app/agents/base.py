"""
Agent 基类。

这里的 Agent 是运行时确定性执行器，不是自由对话型大模型代理。
它们的职责是消费系统内已经结构化的事实，做自动确认、汇总、推送、
催报等明确动作；不负责重建旧总统计人工中间层，也不负责凭空生成业务结论。
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

    AUTO_CONFIRM = "auto_confirm"
    AUTO_REJECT = "auto_reject"
    AUTO_FLAG = "auto_flag"
    AUTO_AGGREGATE = "auto_aggregate"
    AUTO_PUBLISH = "auto_publish"
    AUTO_REMIND = "auto_remind"
    AUTO_RECONCILE = "auto_reconcile"
    AUTO_ALERT = "auto_alert"


@dataclass
class AgentDecision:
    """Agent 决策记录"""

    agent_name: str
    action: AgentAction
    target_type: str
    target_id: int
    reason: str
    details: dict[str, Any] = field(default_factory=dict)
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
        """初始化 Agent 基础信息。"""
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")
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
        """记录一条决策。"""
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
            "%s | %s | %s#%d | %s",
            self.name,
            action.value,
            target_type,
            target_id,
            reason,
        )
        return decision

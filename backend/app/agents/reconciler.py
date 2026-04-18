"""
核对 Agent。
替代旧流程中“人工核对移动端填报与后台生产数据”的环节。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.models.production import MobileShiftReport, ShiftProductionData
from app.rules.thresholds import RECONCILIATION_TOLERANCE_PERCENT


def _to_float(value) -> float | None:
    """将可选数值转换为浮点数。"""

    if value is None:
        return None
    return float(value)


def _percent_diff(left: float | None, right: float | None) -> float:
    """计算两值差异百分比。"""

    if left is None and right is None:
        return 0.0
    if left is None or right is None:
        return 100.0
    baseline = max(abs(left), abs(right), 1e-9)
    return abs(left - right) / baseline * 100.0


def _append_reconcile_note(existing: str | None, reason: str) -> str:
    """在 notes 中追加自动核对说明。"""

    text = f"[自动核对] {reason}"
    if not existing:
        return text
    if text in existing:
        return existing
    return f"{existing}\n{text}"


class ReconcilerAgent(BaseAgent):
    """核对Agent：自动比对移动端报告与后台数据差异。"""

    def __init__(self):
        """初始化核对 Agent。"""
        super().__init__("reconciler")

    def execute(self, *, db: Session, target_date: date) -> list[AgentDecision]:
        """
        核对当日已确认数据。

        规则：
        - 投入/产出差异超过阈值则标记 flagged
        - 出勤人数不一致则标记 flagged
        - 无关联移动端报告则标记 flagged
        - 不提交事务，由调用方控制 commit
        """

        self._decisions = []
        tolerance = float(RECONCILIATION_TOLERANCE_PERCENT)
        rows = (
            db.query(ShiftProductionData)
            .filter(
                ShiftProductionData.business_date == target_date,
                ShiftProductionData.data_status == "confirmed",
            )
            .all()
        )
        if not rows:
            return self._decisions

        production_ids = [int(item.id) for item in rows]
        reports = (
            db.query(MobileShiftReport)
            .filter(MobileShiftReport.linked_production_data_id.in_(production_ids))
            .all()
        )
        report_map = {int(item.linked_production_data_id): item for item in reports if item.linked_production_data_id is not None}

        for item in rows:
            report = report_map.get(int(item.id))
            reasons: list[str] = []

            if report is None:
                reasons.append("无移动端报告关联")
            else:
                input_diff = _percent_diff(_to_float(item.input_weight), _to_float(report.input_weight))
                if input_diff > tolerance:
                    reasons.append(f"投入重量差异 {input_diff:.2f}% 超过阈值 {tolerance:.2f}%")

                output_diff = _percent_diff(_to_float(item.output_weight), _to_float(report.output_weight))
                if output_diff > tolerance:
                    reasons.append(f"产出重量差异 {output_diff:.2f}% 超过阈值 {tolerance:.2f}%")

                if item.actual_headcount != report.attendance_count:
                    reasons.append(
                        f"出勤人数不一致（后台 {item.actual_headcount}，移动端 {report.attendance_count}）"
                    )

            if reasons:
                reason_text = "；".join(reasons)
                item.data_status = "flagged"
                item.notes = _append_reconcile_note(item.notes, reason_text)
                self.record_decision(
                    AgentAction.AUTO_FLAG,
                    "shift_production_data",
                    int(item.id),
                    f"自动核对发现差异：{reason_text}",
                    reasons=reasons,
                )
                continue

            self.logger.info("自动核对通过 | shift_production_data#%s", item.id)
            self.record_decision(
                AgentAction.AUTO_RECONCILE,
                "shift_production_data",
                int(item.id),
                "自动核对通过，差异在阈值内",
            )

        return self._decisions


reconciler_agent = ReconcilerAgent()

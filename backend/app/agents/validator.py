"""
校验 Agent。

职责：
- 在工人提交后做第一时间自动校验
- 给出可执行退回原因
- 把“人肉看一眼再放行”压缩为系统内确定性决策

非职责：
- 不重建旧统计员人工汇总表
- 不替管理层生产合同/发货类旧口径旁路表
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.rules.auto_confirm import evaluate_auto_confirm


class ValidatorAgent(BaseAgent):
    """校验Agent：数据提交后自动校验并确认/退回"""

    def __init__(self):
        """初始化校验 Agent。"""
        super().__init__("validator")

    def execute(
        self,
        *,
        db: Session,
        report_id: int,
        report_data: dict,
        workshop_code: str | None = None,
    ) -> list[AgentDecision]:
        """
        校验并自动确认/退回一条报告。

        流程：
        1. 调用 evaluate_auto_confirm 校验数据
        2. 如果通过：
           - 主路径决策记为 auto_confirmed（兼容字段仍写入 report_status = 'approved'）
           - 更新关联的 ShiftProductionData.data_status = 'confirmed'
           - 记录决策
        3. 如果不通过：
           - 更新 MobileShiftReport.report_status = 'returned'
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
        from app.services.pilot_observability_service import log_pilot_event

        from app.models.production import MobileShiftReport, ShiftProductionData

        report = db.query(MobileShiftReport).filter(MobileShiftReport.id == report_id).first()
        if not report:
            self.logger.warning("Report #%d not found", report_id)
            return self._decisions

        if result.confirmed:
            report.report_status = "approved"
            report.returned_reason = None

            if report.linked_production_data_id:
                spd = (
                    db.query(ShiftProductionData)
                    .filter(ShiftProductionData.id == report.linked_production_data_id)
                    .first()
                )
                if spd:
                    spd.data_status = "confirmed"
                    spd.notes = f"[自动校验通过] {result.reason}"

            self.record_decision(
                AgentAction.AUTO_CONFIRM,
                "mobile_shift_report",
                report_id,
                result.reason,
                warnings=result.validation.warnings,
            )
            log_pilot_event(
                "auto_validation_confirmed",
                report_id=report_id,
                linked_production_data_id=report.linked_production_data_id,
                warning_count=len(result.validation.warnings),
                decision_status="auto_confirmed",
            )
        else:
            report.report_status = "returned"
            report.returned_reason = self._build_returned_reason(result.validation.errors)

            self.record_decision(
                AgentAction.AUTO_REJECT,
                "mobile_shift_report",
                report_id,
                f'校验未通过：{"; ".join(result.validation.errors)}',
                errors=result.validation.errors,
            )
            log_pilot_event(
                "auto_validation_returned",
                report_id=report_id,
                linked_production_data_id=report.linked_production_data_id,
                error_count=len(result.validation.errors),
                decision_status="returned",
                returned_reason=report.returned_reason,
            )

        return self._decisions

    def _build_returned_reason(self, errors: list[str]) -> str:
        """将校验错误整理成工人可直接照着改的退回说明。"""

        if not errors:
            return "请根据提示修改后重新提交。"
        lines = [f"{index}. {message}" for index, message in enumerate(errors, start=1)]
        return "请按以下内容修改后再提交：\n" + "\n".join(lines)


validator_agent = ValidatorAgent()

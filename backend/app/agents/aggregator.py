"""
汇总 Agent。

职责：
- 基于 canonical 生产事实自动形成经营日报
- 输出管理可读摘要与异常摘要

非职责：
- 不把网站重新做回“总统计人工中间台”
- 不把旧人工汇总表原样搬回系统中心；历史口径必须先 canonical 化再进入主工作流
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.config import settings
from app.models.master import Workshop
from app.models.production import ShiftProductionData
from app.models.reports import DailyReport
from app.models.shift import ShiftConfig
from app.services.anomaly_detection_service import detect_daily_anomalies
from app.services import mobile_report_service, report_service
from app.services.pilot_observability_service import log_pilot_event

CANONICAL_SCOPE = "auto_confirmed"


class AggregatorAgent(BaseAgent):
    """汇总Agent：自动汇总已确认数据并生成日报。"""

    def __init__(self):
        """初始化汇总 Agent。"""
        super().__init__("aggregator")

    def execute(self, *, db: Session, target_date: date) -> list[AgentDecision]:
        """
        汇总指定日期生产数据并自动发布日报。

        注意：
        - 幂等：当天已有 published 生产日报时不重复生成
        - confirmed 为 0 时不生成空报告
        - 不提交事务，由调用方控制 commit
        """

        self._decisions = []

        existing_published = (
            db.query(DailyReport)
            .filter(
                DailyReport.report_date == target_date,
                DailyReport.report_type == "production",
                DailyReport.status == "published",
            )
            .first()
        )
        if existing_published is not None:
            self.record_decision(
                AgentAction.AUTO_AGGREGATE,
                "daily_report",
                existing_published.id,
                f"{target_date.isoformat()} 已存在已发布日报，跳过重复生成",
            )
            return self._decisions

        confirmed_count = int(
            db.query(func.count(ShiftProductionData.id))
            .filter(
                ShiftProductionData.business_date == target_date,
                ShiftProductionData.data_status == "confirmed",
            )
            .scalar()
            or 0
        )
        pending_count = int(
            db.query(func.count(ShiftProductionData.id))
            .filter(
                ShiftProductionData.business_date == target_date,
                ShiftProductionData.data_status.in_(("pending", "submitted")),
            )
            .scalar()
            or 0
        )

        workshop_count = int(
            db.query(func.count(Workshop.id)).filter(Workshop.is_active.is_(True)).scalar() or 0
        )
        shift_count = int(
            db.query(func.count(ShiftConfig.id)).filter(ShiftConfig.is_active.is_(True)).scalar() or 0
        )
        total_expected = workshop_count * shift_count

        if confirmed_count == 0:
            self.logger.warning("%s 无已确认班次数据，跳过日报生成", target_date.isoformat())
            log_pilot_event(
                "auto_aggregate_skipped",
                report_date=target_date.isoformat(),
                reason="no_confirmed_data",
            )
            return self._decisions

        production_report = report_service._generate_production_report(
            db,
            report_date=target_date,
            scope=CANONICAL_SCOPE,
        )
        confirmed_count = int(production_report.get("auto_confirmed_shifts", confirmed_count))
        pending_count = int(production_report.get("pending_or_unreported_shifts", pending_count))
        yield_matrix_lane = dict(production_report.get("yield_matrix_lane") or {})

        workshop_rows = (
            db.query(
                ShiftProductionData.workshop_id.label("workshop_id"),
                func.sum(ShiftProductionData.output_weight).label("total_output_weight"),
                func.sum(ShiftProductionData.input_weight).label("total_input_weight"),
                func.sum(ShiftProductionData.electricity_kwh).label("total_electricity_kwh"),
                func.sum(ShiftProductionData.actual_headcount).label("total_actual_headcount"),
            )
            .filter(
                ShiftProductionData.business_date == target_date,
                ShiftProductionData.data_status == "confirmed",
            )
            .group_by(ShiftProductionData.workshop_id)
            .all()
        )

        workshop_ids = [int(item.workshop_id) for item in workshop_rows if item.workshop_id is not None]
        workshop_map = {
            item.id: item.name
            for item in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()
        } if workshop_ids else {}

        workshop_summary: list[dict] = []
        total_output = 0.0
        total_input = 0.0
        total_energy = 0.0
        total_attendance = 0
        for row in workshop_rows:
            output_value = float(row.total_output_weight or 0.0)
            input_value = float(row.total_input_weight or 0.0)
            electricity_value = float(row.total_electricity_kwh or 0.0)
            attendance_value = int(row.total_actual_headcount or 0)
            yield_rate = round((output_value / input_value) * 100, 2) if input_value > 0 else 0.0
            workshop_summary.append(
                {
                    "workshop_id": int(row.workshop_id),
                    "workshop_name": workshop_map.get(int(row.workshop_id), f"车间{row.workshop_id}"),
                    "output_weight": output_value,
                    "input_weight": input_value,
                    "yield_rate": yield_rate,
                    "attendance_count": attendance_value,
                    "electricity_kwh": electricity_value,
                }
            )
            total_output += output_value
            total_input += input_value
            total_energy += electricity_value
            total_attendance += attendance_value

        runtime_yield_rate = round((total_output / total_input) * 100, 2) if total_input > 0 else 0.0
        matrix_ready = yield_matrix_lane.get("quality_status") == "ready"
        matrix_company_total = yield_matrix_lane.get("company_total_yield") if matrix_ready else None
        overall_yield_rate = float(matrix_company_total) if matrix_company_total is not None else runtime_yield_rate
        reporting_rate = round((confirmed_count / total_expected) * 100, 2) if total_expected > 0 else 100.0
        missing_tip = f"注意：{pending_count}个班次待补报或未闭环。" if pending_count > 0 else ""
        boss_summary = (
            f"{target_date.strftime('%Y-%m-%d')} 生产日报：今日产量 {total_output:.2f} 吨，上报率 {reporting_rate:.2f}%，"
            f"成材率 {overall_yield_rate:.2f}%，出勤 {total_attendance} 人。{missing_tip}"
        ).strip()

        _ = report_service._build_boss_text_summary(db, report_date=target_date, scope=CANONICAL_SCOPE)
        mobile_summary = mobile_report_service.summarize_mobile_reporting(db, target_date=target_date)
        anomaly_payload = detect_daily_anomalies(db, target_date=target_date)
        anomaly_summary = anomaly_payload.get("summary", {})
        anomaly_text = anomaly_summary.get("digest", "未发现关键异常")
        boss_summary = f"{boss_summary}。异常：{anomaly_text}"

        entity = (
            db.query(DailyReport)
            .filter(DailyReport.report_date == target_date, DailyReport.report_type == "production")
            .first()
        )
        if entity is None:
            entity = DailyReport(report_date=target_date, report_type="production")
            db.add(entity)
            db.flush()

        entity.report_data = {
            "report_date": target_date.isoformat(),
            "confirmed_count": confirmed_count,
            "pending_count": pending_count,
            "total_expected": total_expected,
            "reporting_rate": reporting_rate,
            "total_output_weight": total_output,
            "total_input_weight": total_input,
            "yield_rate": overall_yield_rate,
            "yield_rate_source": "yield_matrix_lane" if matrix_company_total is not None else "runtime_work_order",
            "total_attendance": total_attendance,
            "total_electricity_kwh": total_energy,
            "workshops": workshop_summary,
            "mobile_reporting_summary": mobile_summary,
            "anomaly_summary": anomaly_summary,
            "anomaly_items": anomaly_payload.get("items", []),
            "yield_matrix_lane": yield_matrix_lane,
            "boss_summary": boss_summary,
        }
        entity.text_summary = boss_summary
        entity.generated_scope = production_report.get("canonical_scope", CANONICAL_SCOPE)
        entity.output_mode = "both"
        entity.generated_at = datetime.now(timezone.utc)
        entity.final_text_summary = boss_summary

        self.record_decision(
            AgentAction.AUTO_AGGREGATE,
            "daily_report",
            entity.id,
            f"自动汇总完成：{target_date.isoformat()}，已确认 {confirmed_count} 班次",
            confirmed_count=confirmed_count,
            pending_count=pending_count,
            total_expected=total_expected,
        )
        if settings.AUTO_PUBLISH_ENABLED:
            entity.status = "published"
            entity.published_by = None
            entity.published_at = datetime.now(timezone.utc)
            self.record_decision(
                AgentAction.AUTO_PUBLISH,
                "daily_report",
                entity.id,
                f"自动发布完成：{boss_summary}",
            )
            log_pilot_event(
                "auto_publish_completed",
                report_id=entity.id,
                report_date=target_date.isoformat(),
                confirmed_count=confirmed_count,
                pending_count=pending_count,
            )
        else:
            entity.status = "reviewed"
            entity.published_by = None
            entity.published_at = None
            log_pilot_event(
                "auto_publish_skipped",
                report_id=entity.id,
                report_date=target_date.isoformat(),
                reason="AUTO_PUBLISH_ENABLED=false",
            )

        log_pilot_event(
            "auto_aggregate_completed",
            report_id=entity.id,
            report_date=target_date.isoformat(),
            confirmed_count=confirmed_count,
            pending_count=pending_count,
            reporting_rate=reporting_rate,
            anomaly_total=int(anomaly_summary.get("total", 0)),
            anomaly_digest=anomaly_summary.get("digest", ""),
        )
        return self._decisions


aggregator_agent = AggregatorAgent()

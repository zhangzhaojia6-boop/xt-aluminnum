"""异常检测服务。
用于替代人工核对环节，自动发现最小异常清单并输出摘要。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.core.anomaly_types import ANOMALY_TYPE_DICT, anomaly_meta
from app.models.attendance import AttendanceSchedule
from app.models.production import MobileShiftReport, ShiftProductionData
from app.models.shift import ShiftConfig

READY_REPORT_STATUSES = {"submitted", "approved", "auto_confirmed"}


def _to_float(value: Any) -> float | None:
    """将数值安全转换为浮点数。"""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _base_anomaly(
    *,
    anomaly_type: str,
    title: str,
    detail: str,
    workshop_id: int | None,
    shift_id: int | None,
    team_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> dict[str, Any]:
    """构建统一异常结构。"""

    meta = anomaly_meta(anomaly_type)
    return {
        "anomaly_type": anomaly_type,
        "label": meta.get("label", anomaly_type),
        "severity": meta.get("severity", "medium"),
        "title": title,
        "detail": detail,
        "workshop_id": workshop_id,
        "shift_id": shift_id,
        "team_id": team_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "suggested_action": meta.get("suggested_action", ""),
    }


def detect_output_gt_input_anomalies(report_rows: Iterable[Any]) -> list[dict[str, Any]]:
    """检测“产出大于投入”异常。"""

    results: list[dict[str, Any]] = []
    for row in report_rows:
        input_weight = _to_float(getattr(row, "input_weight", None))
        output_weight = _to_float(getattr(row, "output_weight", None))
        if input_weight is None or output_weight is None:
            continue
        if output_weight <= input_weight:
            continue
        results.append(
            _base_anomaly(
                anomaly_type="output_gt_input",
                title="产出大于投入",
                detail=f"产出 {output_weight:.3f} 吨，高于投入 {input_weight:.3f} 吨。",
                workshop_id=getattr(row, "workshop_id", None),
                shift_id=getattr(row, "shift_config_id", None),
                team_id=getattr(row, "team_id", None),
                entity_type="mobile_shift_report",
                entity_id=getattr(row, "id", None),
            )
        )
    return results


def detect_shift_missing_report_anomalies(expected_rows: Iterable[Any], report_rows: Iterable[Any]) -> list[dict[str, Any]]:
    """检测“班次缺报”异常。"""

    ready_key_set: set[tuple[date, int, int, int | None]] = set()
    for row in report_rows:
        status = getattr(row, "report_status", None)
        if status not in READY_REPORT_STATUSES:
            continue
        ready_key_set.add(
            (
                getattr(row, "business_date"),
                int(getattr(row, "shift_config_id")),
                int(getattr(row, "workshop_id")),
                getattr(row, "team_id"),
            )
        )

    results: list[dict[str, Any]] = []
    for row in expected_rows:
        key = (
            getattr(row, "business_date"),
            int(getattr(row, "shift_config_id")),
            int(getattr(row, "workshop_id")),
            getattr(row, "team_id"),
        )
        if key in ready_key_set:
            continue
        results.append(
            _base_anomaly(
                anomaly_type="shift_missing_report",
                title="班次缺报",
                detail=f"班次 {key[1]} 在 {key[0]} 未完成提交。",
                workshop_id=key[2],
                shift_id=key[1],
                team_id=key[3],
                entity_type="attendance_schedule",
                entity_id=None,
            )
        )
    return results


def detect_energy_spike_anomalies(
    current_rows: Iterable[Any],
    history_avg_map: dict[tuple[int, int], float],
    *,
    spike_factor: float = 1.5,
    min_delta: float = 100.0,
) -> list[dict[str, Any]]:
    """检测“能耗异常波动”异常。"""

    results: list[dict[str, Any]] = []
    for row in current_rows:
        key = (int(getattr(row, "workshop_id")), int(getattr(row, "shift_config_id")))
        current_energy = _to_float(getattr(row, "electricity_kwh", None))
        history_avg = _to_float(history_avg_map.get(key))
        if current_energy is None or history_avg is None or history_avg <= 0:
            continue
        if current_energy < history_avg * spike_factor:
            continue
        if current_energy - history_avg < min_delta:
            continue
        results.append(
            _base_anomaly(
                anomaly_type="energy_spike",
                title="能耗异常波动",
                detail=f"当前能耗 {current_energy:.2f}，近7日均值 {history_avg:.2f}。",
                workshop_id=getattr(row, "workshop_id", None),
                shift_id=getattr(row, "shift_config_id", None),
                team_id=getattr(row, "team_id", None),
                entity_type="shift_production_data",
                entity_id=getattr(row, "id", None),
            )
        )
    return results


def detect_attendance_anomalies(current_rows: Iterable[Any]) -> list[dict[str, Any]]:
    """检测“出勤异常”异常。"""

    results: list[dict[str, Any]] = []
    for row in current_rows:
        planned = getattr(row, "planned_headcount", None)
        actual = getattr(row, "actual_headcount", None)
        if actual is None:
            continue
        if int(actual) <= 0:
            results.append(
                _base_anomaly(
                    anomaly_type="attendance_abnormal",
                    title="出勤异常",
                    detail=f"实际出勤为 {actual}，请核对是否漏填。",
                    workshop_id=getattr(row, "workshop_id", None),
                    shift_id=getattr(row, "shift_config_id", None),
                    team_id=getattr(row, "team_id", None),
                    entity_type="shift_production_data",
                    entity_id=getattr(row, "id", None),
                )
            )
            continue
        if planned in (None, 0):
            continue
        ratio = abs(int(actual) - int(planned)) / max(int(planned), 1)
        if ratio >= 0.4:
            results.append(
                _base_anomaly(
                    anomaly_type="attendance_abnormal",
                    title="出勤异常",
                    detail=f"计划出勤 {planned}，实际 {actual}，偏差 {ratio * 100:.1f}%。",
                    workshop_id=getattr(row, "workshop_id", None),
                    shift_id=getattr(row, "shift_config_id", None),
                    team_id=getattr(row, "team_id", None),
                    entity_type="shift_production_data",
                    entity_id=getattr(row, "id", None),
                )
            )
    return results


def detect_cross_shift_jump_anomalies(
    current_rows: Iterable[Any],
    shift_sort_map: dict[int, int],
    *,
    jump_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """检测“跨班次跳变”异常。"""

    grouped: dict[int, list[Any]] = defaultdict(list)
    for row in current_rows:
        grouped[int(getattr(row, "workshop_id"))].append(row)

    results: list[dict[str, Any]] = []
    for workshop_id, rows in grouped.items():
        ordered = sorted(
            rows,
            key=lambda item: (
                shift_sort_map.get(int(getattr(item, "shift_config_id")), 9999),
                int(getattr(item, "shift_config_id")),
            ),
        )
        previous_output: float | None = None
        for row in ordered:
            output_value = _to_float(getattr(row, "output_weight", None))
            if output_value is None:
                continue
            if previous_output is not None and previous_output > 0:
                ratio = abs(output_value - previous_output) / previous_output
                if ratio >= jump_threshold:
                    results.append(
                        _base_anomaly(
                            anomaly_type="cross_shift_jump",
                            title="跨班次跳变",
                            detail=f"相邻班次产出从 {previous_output:.2f} 跳变到 {output_value:.2f}，偏差 {ratio * 100:.1f}%。",
                            workshop_id=workshop_id,
                            shift_id=getattr(row, "shift_config_id", None),
                            team_id=getattr(row, "team_id", None),
                            entity_type="shift_production_data",
                            entity_id=getattr(row, "id", None),
                        )
                    )
            previous_output = output_value
    return results


def summarize_anomalies(items: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总异常清单。"""

    by_type: dict[str, int] = defaultdict(int)
    for item in items:
        by_type[str(item.get("anomaly_type"))] += 1
    sorted_types = sorted(by_type.items(), key=lambda pair: pair[1], reverse=True)
    top_lines = [f"{ANOMALY_TYPE_DICT.get(code, {}).get('label', code)} {count}条" for code, count in sorted_types[:3]]
    digest = "；".join(top_lines) if top_lines else "未发现关键异常"
    return {
        "total": len(items),
        "by_type": dict(sorted_types),
        "digest": digest,
    }


def detect_daily_anomalies(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
    max_items: int = 100,
) -> dict[str, Any]:
    """检测指定日期的最小异常闭环清单。"""

    report_query = db.query(MobileShiftReport).filter(MobileShiftReport.business_date == target_date)
    schedule_query = (
        db.query(
            AttendanceSchedule.business_date,
            AttendanceSchedule.shift_config_id,
            AttendanceSchedule.workshop_id,
            AttendanceSchedule.team_id,
        )
        .filter(
            AttendanceSchedule.business_date == target_date,
            AttendanceSchedule.shift_config_id.is_not(None),
            AttendanceSchedule.workshop_id.is_not(None),
        )
        .distinct()
    )
    current_spd_query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == target_date,
        ShiftProductionData.data_status != "voided",
    )
    if workshop_id is not None:
        report_query = report_query.filter(MobileShiftReport.workshop_id == workshop_id)
        schedule_query = schedule_query.filter(AttendanceSchedule.workshop_id == workshop_id)
        current_spd_query = current_spd_query.filter(ShiftProductionData.workshop_id == workshop_id)

    report_rows = report_query.all()
    expected_rows = schedule_query.all()
    current_spd_rows = current_spd_query.all()

    history_start = target_date - timedelta(days=7)
    history_query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date >= history_start,
        ShiftProductionData.business_date < target_date,
        ShiftProductionData.data_status != "voided",
    )
    if workshop_id is not None:
        history_query = history_query.filter(ShiftProductionData.workshop_id == workshop_id)
    history_rows = history_query.all()

    history_avg_map: dict[tuple[int, int], float] = {}
    history_bucket: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in history_rows:
        energy = _to_float(getattr(row, "electricity_kwh", None))
        if energy is None:
            continue
        key = (int(getattr(row, "workshop_id")), int(getattr(row, "shift_config_id")))
        history_bucket[key].append(energy)
    for key, values in history_bucket.items():
        history_avg_map[key] = sum(values) / len(values)

    shift_ids = {int(getattr(row, "shift_config_id")) for row in current_spd_rows}
    shift_rows = db.query(ShiftConfig).filter(ShiftConfig.id.in_(tuple(shift_ids))).all() if shift_ids else []
    shift_sort_map = {int(row.id): int(getattr(row, "sort_order", row.id)) for row in shift_rows}

    anomalies: list[dict[str, Any]] = []
    anomalies.extend(detect_output_gt_input_anomalies(report_rows))
    anomalies.extend(detect_shift_missing_report_anomalies(expected_rows, report_rows))
    anomalies.extend(detect_energy_spike_anomalies(current_spd_rows, history_avg_map))
    anomalies.extend(detect_attendance_anomalies(current_spd_rows))
    anomalies.extend(detect_cross_shift_jump_anomalies(current_spd_rows, shift_sort_map))

    summary = summarize_anomalies(anomalies)
    return {
        "date": target_date.isoformat(),
        "workshop_id": workshop_id,
        "summary": summary,
        "items": anomalies[: max(1, max_items)],
        "definitions": ANOMALY_TYPE_DICT,
    }

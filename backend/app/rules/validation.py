"""
数据校验规则集。
当工人提交数据时，校验 Agent 调用这些规则判断数据是否合格，
替代旧流程中的人工核对与退回说明。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ValidationResult:
    """校验结果"""

    passed: bool
    errors: list[str]
    warnings: list[str]


def _is_missing(value: Any) -> bool:
    """判断字段是否缺失。"""

    return value is None or value == ""


def _to_float(value: Any) -> float | None:
    """将输入值转换为浮点数，无法转换时返回空。"""

    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_threshold(key: str, *, workshop_code: str | None, db: Session | None):
    from app.services import rule_config_service

    return rule_config_service.resolve_threshold(key, workshop_code=workshop_code, db=db)


def _rule_tag(key: str, *, workshop_code: str | None, db: Session | None) -> str:
    resolved = _resolve_threshold(key, workshop_code=workshop_code, db=db)
    if resolved.scope_type == 'workshop' and resolved.scope_key:
        scope = resolved.scope_key
    elif resolved.source == 'fallback' and workshop_code:
        scope = workshop_code
    else:
        scope = 'factory'
    return f"[规则:{key}@{scope}]"


def validate_shift_report(
    data: dict,
    *,
    workshop_code: str | None = None,
    db: Session | None = None,
) -> ValidationResult:
    """
    校验班次报告数据。

    规则：
    1. 必填字段检查：attendance_count, input_weight, output_weight 必须有值
    2. 数值范围检查：所有重量字段 >= 0
    3. 逻辑一致性：output_weight <= input_weight
    4. 合理范围：attendance_count 在 1-50 之间
    5. electricity_daily >= 0（如果填了）
    6. gas_daily >= 0（如果填了）

    参数：
        data: 报告数据字典
        workshop_code: 车间编码，用于读取车间阈值覆盖

    返回：
        ValidationResult 对象
    """

    errors: list[str] = []
    warnings: list[str] = []
    min_attendance = _resolve_threshold('MIN_ATTENDANCE', workshop_code=workshop_code, db=db).value
    max_attendance = _resolve_threshold('MAX_ATTENDANCE', workshop_code=workshop_code, db=db).value
    min_weight = _resolve_threshold('MIN_WEIGHT', workshop_code=workshop_code, db=db).value
    max_single_shift_weight = _resolve_threshold('MAX_SINGLE_SHIFT_WEIGHT', workshop_code=workshop_code, db=db).value
    min_energy = _resolve_threshold('MIN_ENERGY', workshop_code=workshop_code, db=db).value
    max_electricity_daily = _resolve_threshold('MAX_ELECTRICITY_DAILY', workshop_code=workshop_code, db=db).value
    max_gas_daily = _resolve_threshold('MAX_GAS_DAILY', workshop_code=workshop_code, db=db).value

    attendance_value = data.get("attendance_count")
    if _is_missing(attendance_value):
        errors.append("出勤人数未填写。请填写本班实际到岗人数。")
        attendance_count: int | None = None
    else:
        try:
            attendance_count = int(attendance_value)
        except (TypeError, ValueError):
            attendance_count = None
            errors.append("出勤人数格式不正确。请只填写数字。")
        else:
            if attendance_count < min_attendance:
                errors.append(f"出勤人数不能小于{min_attendance:g}。请填写实际到岗人数。 {_rule_tag('MIN_ATTENDANCE', workshop_code=workshop_code, db=db)}")
            elif attendance_count > max_attendance:
                warnings.append(f"出勤人数偏高（超过{max_attendance:g}）。请核对是否多填。 {_rule_tag('MAX_ATTENDANCE', workshop_code=workshop_code, db=db)}")

    numeric_fields = {
        "input_weight": "投入重量",
        "output_weight": "产出重量",
        "scrap_weight": "废料重量",
    }
    numeric_values: dict[str, float | None] = {}
    for field_name, field_label in numeric_fields.items():
        value = data.get(field_name)
        if field_name in {"input_weight", "output_weight"} and _is_missing(value):
            errors.append(f"{field_label}未填写。请填写本班实际吨数。")
            numeric_values[field_name] = None
            continue

        numeric_value = _to_float(value)
        numeric_values[field_name] = numeric_value
        if numeric_value is None:
            if not _is_missing(value):
                errors.append(f"{field_label}格式不正确。请填写数字（示例：12.5）。")
            continue
        if numeric_value < min_weight:
            errors.append(f"{field_label}不能小于{min_weight:g}。请改为实际吨数。 {_rule_tag('MIN_WEIGHT', workshop_code=workshop_code, db=db)}")
        elif numeric_value > max_single_shift_weight:
            errors.append(f"{field_label}超过单班上限{max_single_shift_weight:g}吨。请核对后重填。 {_rule_tag('MAX_SINGLE_SHIFT_WEIGHT', workshop_code=workshop_code, db=db)}")

    input_weight = numeric_values.get("input_weight")
    output_weight = numeric_values.get("output_weight")
    if input_weight is not None and output_weight is not None and output_weight > input_weight:
        errors.append("产出重量大于投入重量。请核对后把产出改为不大于投入。")

    electricity_daily = _to_float(data.get("electricity_daily"))
    if electricity_daily is None:
        if not _is_missing(data.get("electricity_daily")):
            warnings.append("日电耗格式不正确，系统未计入。请改成数字后再提交更准确。")
    else:
        if electricity_daily < min_energy:
            errors.append(f"日电耗不能小于{min_energy:g}。请改为实际用电量。 {_rule_tag('MIN_ENERGY', workshop_code=workshop_code, db=db)}")
        elif electricity_daily > max_electricity_daily:
            warnings.append(f"日电耗偏高（超过{max_electricity_daily:g}）。请核对是否填错。 {_rule_tag('MAX_ELECTRICITY_DAILY', workshop_code=workshop_code, db=db)}")

    gas_daily = _to_float(data.get("gas_daily"))
    if gas_daily is None:
        if not _is_missing(data.get("gas_daily")):
            warnings.append("日燃气用量格式不正确，系统未计入。请改成数字后再提交更准确。")
    else:
        if gas_daily < min_energy:
            errors.append(f"日燃气用量不能小于{min_energy:g}。请改为实际用量。 {_rule_tag('MIN_ENERGY', workshop_code=workshop_code, db=db)}")
        elif gas_daily > max_gas_daily:
            warnings.append(f"日燃气用量偏高（超过{max_gas_daily:g}）。请核对是否填错。 {_rule_tag('MAX_GAS_DAILY', workshop_code=workshop_code, db=db)}")

    return ValidationResult(
        passed=not errors,
        errors=errors,
        warnings=warnings,
    )

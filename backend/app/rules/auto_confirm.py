"""
自动确认规则。
当数据通过所有校验规则后，自动将状态设为自动确认，
替代旧流程中的人工审核确认。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rules.validation import ValidationResult, validate_shift_report


@dataclass(frozen=True)
class AutoConfirmResult:
    """自动确认结果"""

    confirmed: bool
    validation: ValidationResult
    reason: str


def evaluate_auto_confirm(data: dict, *, workshop_code: str | None = None) -> AutoConfirmResult:
    """
    评估是否自动确认。

    流程：
    1. 调用 validate_shift_report 校验
    2. 如果校验全部通过，则 confirmed=True
    3. 如果有 errors，则 confirmed=False
    4. warnings 不阻止确认，但会写入 reason

    返回：
        AutoConfirmResult 对象
    """

    validation = validate_shift_report(data, workshop_code=workshop_code)
    if validation.errors:
        return AutoConfirmResult(
            confirmed=False,
            validation=validation,
            reason=f"校验未通过：{'；'.join(validation.errors)}",
        )

    if validation.warnings:
        return AutoConfirmResult(
            confirmed=True,
            validation=validation,
            reason=f"自动校验通过，但请留意：{'；'.join(validation.warnings)}",
        )

    return AutoConfirmResult(
        confirmed=True,
        validation=validation,
        reason="自动校验通过",
    )

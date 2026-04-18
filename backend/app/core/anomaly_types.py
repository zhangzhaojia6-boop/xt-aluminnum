"""异常类型字典。
用于替代人工口头对齐异常口径，统一异常编码、说明和处理建议。
"""

from __future__ import annotations

from typing import Any


ANOMALY_TYPE_DICT: dict[str, dict[str, Any]] = {
    "output_gt_input": {
        "label": "产出大于投入",
        "severity": "high",
        "description": "同一班次产出重量高于投入重量。",
        "suggested_action": "请班组核对投入与产出重量后重新提交。",
    },
    "shift_missing_report": {
        "label": "班次缺报",
        "severity": "high",
        "description": "应报班次未完成填报提交。",
        "suggested_action": "请班组立即补报当班数据。",
    },
    "energy_spike": {
        "label": "能耗异常波动",
        "severity": "medium",
        "description": "能耗相对近7日均值出现显著抬升。",
        "suggested_action": "请核对设备状态与能耗录入是否异常。",
    },
    "attendance_abnormal": {
        "label": "出勤异常",
        "severity": "medium",
        "description": "实际出勤偏离计划或出现无效人数。",
        "suggested_action": "请核对排班与实际到岗人数。",
    },
    "cross_shift_jump": {
        "label": "跨班次跳变",
        "severity": "medium",
        "description": "同车间相邻班次产出出现突变。",
        "suggested_action": "请核对机台状态、原料与班次交接记录。",
    },
}


def anomaly_meta(anomaly_type: str) -> dict[str, Any]:
    """获取异常类型元信息。"""

    return dict(ANOMALY_TYPE_DICT.get(anomaly_type, {}))


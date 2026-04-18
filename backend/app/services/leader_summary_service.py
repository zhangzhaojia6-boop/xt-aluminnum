from __future__ import annotations

from datetime import date
from typing import Any

from app.adapters.llm import generate_llm_summary
from app.config import Settings, settings as runtime_settings


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_leader_summary_metrics(*, report_date: date, report_data: dict[str, Any]) -> dict[str, Any]:
    yield_matrix_lane = dict(report_data.get('yield_matrix_lane') or {})
    contract_lane = dict(report_data.get('contract_lane') or {})
    anomaly_summary = dict(report_data.get('anomaly_summary') or {})
    inventory_lane = list(report_data.get('inventory_lane') or [])

    company_total_yield = (
        yield_matrix_lane.get('company_total_yield')
        if yield_matrix_lane.get('quality_status') == 'ready'
        else report_data.get('yield_rate')
    )
    in_process_weight = sum(_to_float(item.get('storage_prepared')) for item in inventory_lane)
    consumable_weight = sum(_to_float(item.get('storage_finished')) for item in inventory_lane)
    shipment_weight = sum(_to_float(item.get('shipment_weight')) for item in inventory_lane)
    storage_inbound_area = sum(_to_float(item.get('storage_inbound_area')) for item in inventory_lane)

    return {
        'report_date': report_date.isoformat(),
        'total_output_weight': round(_to_float(report_data.get('total_output_weight')), 2),
        'total_energy': round(_to_float(report_data.get('total_electricity_kwh') or report_data.get('total_energy')), 2),
        'energy_per_ton': round(_to_float(report_data.get('energy_per_ton')), 2),
        'reporting_rate': round(_to_float(report_data.get('reporting_rate')), 2),
        'total_attendance': _to_int(report_data.get('total_attendance')),
        'contract_weight': round(_to_float(contract_lane.get('daily_contract_weight')), 2),
        'yield_rate': round(_to_float(company_total_yield), 2),
        'anomaly_total': _to_int(anomaly_summary.get('total')),
        'anomaly_digest': str(anomaly_summary.get('digest') or '未发现关键异常'),
        'in_process_weight': round(in_process_weight, 2),
        'consumable_weight': round(consumable_weight, 2),
        'shipment_weight': round(shipment_weight, 2),
        'storage_inbound_area': round(storage_inbound_area, 2),
    }


def build_deterministic_leader_summary(*, metrics: dict[str, Any]) -> str:
    return (
        f"{metrics['report_date']}，今日产量 {metrics['total_output_weight']:.2f} 吨，"
        f"单吨能耗 {metrics['energy_per_ton']:.2f}，"
        f"在制料 {metrics['in_process_weight']:.2f}，耗材/入库 {metrics['consumable_weight']:.2f}，"
        f"发货 {metrics['shipment_weight']:.2f} 吨，入库面积 {metrics['storage_inbound_area']:.2f} ㎡，"
        f"出勤 {metrics['total_attendance']} 人，合同量 {metrics['contract_weight']:.2f} 吨，"
        f"成品率 {metrics['yield_rate']:.2f}%，"
        f"异常 {metrics['anomaly_total']} 条（{metrics['anomaly_digest']}）。"
    )


def build_best_effort_leader_summary(
    *,
    report_date: date,
    report_data: dict[str, Any],
    settings: Settings | None = None,
    llm_client=None,
) -> dict[str, Any]:
    runtime = settings or runtime_settings
    metrics = build_leader_summary_metrics(report_date=report_date, report_data=report_data)
    fallback = build_deterministic_leader_summary(metrics=metrics)

    result = {
        'summary_text': fallback,
        'summary_source': 'deterministic',
        'metrics': metrics,
        'llm_enabled': bool(runtime.LLM_ENABLED),
        'llm_error': None,
    }
    if not runtime.LLM_ENABLED:
        return result

    try:
        summary = generate_llm_summary(
            messages=[
                {
                    'role': 'system',
                    'content': '你是工厂经营日报助手。只能基于给定事实生成简洁中文摘要，不能编造任何新事实。',
                },
                {
                    'role': 'user',
                    'content': (
                        '请基于以下 JSON 事实生成 80-140 字中文领导摘要，只输出摘要正文：\n'
                        f'{metrics}'
                    ),
                },
            ],
            settings=runtime,
            client=llm_client,
        )
    except Exception as exc:  # noqa: BLE001
        result['llm_error'] = f'{exc.__class__.__name__}: {exc}'
        return result

    result['summary_text'] = summary
    result['summary_source'] = 'llm'
    return result

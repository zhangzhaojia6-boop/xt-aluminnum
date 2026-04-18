from __future__ import annotations

from typing import Any


YIELD_RATE_DEPRECATION_MAP: list[dict[str, Any]] = [
    {
        'surface_id': 'daily_report.formal_yield_rate',
        'category': 'page_display',
        'location': 'frontend/src/views/reports/ReportDetail.vue',
        'status': 'replace',
        'replacement': 'report_data.yield_matrix_lane.company_total_yield when quality_status=ready',
        'notes': '正式日报成材率应优先读矩阵公司总成品率，不再把旧 report_data.yield_rate 当唯一正式真相。',
    },
    {
        'surface_id': 'live_dashboard.local_yield_recalc',
        'category': 'page_display',
        'location': 'frontend/src/views/reports/LiveDashboard.vue',
        'status': 'remove',
        'replacement': 'backend realtime aggregation payload',
        'notes': '前端本地 calcYield/recomputeAggregation 已收敛；正式成材率由后端 authoritative payload 提供。',
    },
    {
        'surface_id': 'realtime.factory_workshop_yield_rate',
        'category': 'service_rule',
        'location': 'backend/app/services/realtime_service.py',
        'status': 'replace',
        'replacement': 'yield_matrix_lane for factory/workshop totals; runtime values remain compat for machine/shift/detail',
        'notes': '全厂与车间 totals 视为正式观察面，优先使用矩阵口径；机台/班次明细暂保留 runtime compat。',
    },
    {
        'surface_id': 'report_push.summary_yield_rate',
        'category': 'automation_copy',
        'location': 'backend/app/agents/reporter.py',
        'status': 'replace',
        'replacement': 'yield_matrix_lane.company_total_yield when ready',
        'notes': '自动推送文案不能继续默认旧 runtime yield_rate 为正式口径。',
    },
    {
        'surface_id': 'work_order_entries.yield_rate',
        'category': 'raw_runtime',
        'location': 'backend/app/models/production.py -> WorkOrderEntry.yield_rate',
        'status': 'compat_only',
        'replacement': 'retain as local runtime/raw calculation until matrix convergence for detail surfaces',
        'notes': '暂不删除数据库字段；仅降级为兼容/原始计算字段，不再承担正式管理口径。',
    },
    {
        'surface_id': 'workshop_templates.readonly_yield_rate',
        'category': 'schema_display',
        'location': 'backend/app/core/workshop_templates.py',
        'status': 'compat_only',
        'replacement': 'keep as readonly runtime field until mobile/detail forms fully converge',
        'notes': '模板只读成品率仍可保留给现场录入参考，但不再代表正式管理成品率。',
    },
]


def build_yield_rate_deprecation_map() -> dict[str, Any]:
    replace_count = len([item for item in YIELD_RATE_DEPRECATION_MAP if item['status'] == 'replace'])
    compat_only_count = len([item for item in YIELD_RATE_DEPRECATION_MAP if item['status'] == 'compat_only'])
    remove_count = len([item for item in YIELD_RATE_DEPRECATION_MAP if item['status'] == 'remove'])
    return {
        'version': 1,
        'formal_truth': 'yield_matrix_lane',
        'statuses': {
            'replace': replace_count,
            'compat_only': compat_only_count,
            'remove': remove_count,
        },
        'items': list(YIELD_RATE_DEPRECATION_MAP),
    }

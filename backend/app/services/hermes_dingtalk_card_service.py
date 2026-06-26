from __future__ import annotations

from typing import Any

from app.services.hermes_factory_brain_types import FactoryBrainProgress


_STAGES = [
    ('received', '已接收'),
    ('recognized', '已识别业务意图'),
    ('querying', '正在查询数据源'),
    ('validating', '正在校验口径'),
    ('generating', '正在生成结果'),
    ('completed', '已完成'),
    ('feedback', '等待反馈'),
]


def build_progress_sequence(trace_id: str, title: str) -> list[FactoryBrainProgress]:
    return [
        FactoryBrainProgress(
            stage=stage,
            title=title,
            details=[label],
            trace_id=trace_id,
        )
        for stage, label in _STAGES
    ]


def build_progress_card(progress: FactoryBrainProgress) -> dict[str, Any]:
    return {
        'cardBizId': f'hermes-factory-brain-{progress.trace_id}',
        'title': progress.title,
        'stage': progress.stage,
        'details': list(progress.details),
        'actions': [
            {'key': 'view_sources', 'label': '查看来源'},
            {'key': 'rerun', 'label': '重新查询'},
            {'key': 'accept', 'label': '采纳结果'},
            {'key': 'mark_inaccurate', 'label': '标记不准'},
        ],
    }

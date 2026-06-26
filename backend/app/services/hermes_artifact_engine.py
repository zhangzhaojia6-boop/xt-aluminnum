from __future__ import annotations

from app.services.hermes_factory_brain_types import (
    FactoryBrainArtifactRequest,
    FactoryBrainDataReference,
    FactoryBrainNormalizedRequest,
)


def plan_artifacts(
    normalized: FactoryBrainNormalizedRequest,
    references: list[FactoryBrainDataReference],
) -> list[FactoryBrainArtifactRequest]:
    text = normalized.normalized_text
    if any(token in text for token in ('图片', '图像', '封面', '知识卡片')):
        return [
            FactoryBrainArtifactRequest(
                artifact_type='image',
                title='Hermes 图像生成请求',
                format='image_api_request',
                payload={
                    'prompt_basis': text,
                    'generated_image_is_real_photo': False,
                    'source_count': len(references),
                },
            )
        ]
    if any(token in text for token in ('文档', 'PDF', '月报', '年报')):
        return [
            FactoryBrainArtifactRequest(
                artifact_type='document',
                title='Hermes 业务文档',
                format='pdf',
                payload={'source_count': len(references), 'metrics': normalized.metrics},
            )
        ]
    if any(token in text for token in ('图表', '趋势', '对比')):
        return [
            FactoryBrainArtifactRequest(
                artifact_type='chart',
                title='Hermes 业务图表',
                format='png',
                payload={'source_count': len(references), 'metrics': normalized.metrics},
            )
        ]
    return [
        FactoryBrainArtifactRequest(
            artifact_type='table',
            title='Hermes 业务表格',
            format='xlsx',
            payload={'source_count': len(references), 'metrics': normalized.metrics},
        )
    ]

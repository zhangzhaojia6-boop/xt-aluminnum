from __future__ import annotations

import re
from datetime import date, timedelta

from app.services.hermes_factory_brain_types import FactoryBrainIntent


def classify_factory_brain_intent(text: str, *, today: date) -> FactoryBrainIntent:
    clean = str(text or '').strip()
    business_date = _extract_business_date(clean, today=today)

    if _looks_like_long_term_rule(clean):
        return FactoryBrainIntent(
            intent_type='long_term_rule',
            task_type='rule_management',
            domain='governance',
            business_date=business_date,
            requires_root_owner=True,
        )
    if '日报' in clean:
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='daily_report',
            domain='production',
            business_date=business_date,
            requires_root_owner=True,
        )
    if any(token in clean for token in ('为什么高', '异常', '电耗', '气耗', '成品率')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='anomaly_analysis',
            domain='process_quality',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('合同', '发货', '库存', '交付')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='business_question',
            domain='operations',
            business_date=business_date,
        )
    if clean in {'在干嘛', '你在干嘛'}:
        return FactoryBrainIntent(
            intent_type='contextual_intent',
            task_type='current_status',
            domain='general',
            business_date=business_date,
        )
    if '产量' in clean and any(token in clean for token in ('出来', '有了吗', '了吗')):
        return FactoryBrainIntent(
            intent_type='contextual_intent',
            task_type='production_readiness',
            domain='production',
            business_date=business_date,
        )
    return FactoryBrainIntent(
        intent_type='general_chat',
        task_type='conversation',
        domain='general',
        business_date=business_date,
    )


def _looks_like_long_term_rule(text: str) -> bool:
    return any(token in text for token in ('以后', '记住', '长期规则', '作为规则', '不要记住', '临时口径'))


def _extract_business_date(text: str, *, today: date) -> date:
    match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    if match:
        return date(today.year, int(match.group(1)), int(match.group(2)))
    if '昨天' in text or '昨日' in text:
        return today - timedelta(days=1)
    return today


def _extract_entities(text: str) -> dict[str, str]:
    entities: dict[str, str] = {}
    workshop = re.search(r'(1650|1850|2050)', text)
    if workshop:
        entities['workshop'] = workshop.group(1)
    if '电耗' in text:
        entities['metric'] = 'electricity_per_ton'
    if '气耗' in text:
        entities['metric'] = 'gas_per_ton'
    return entities

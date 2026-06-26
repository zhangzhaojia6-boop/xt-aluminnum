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
    if _looks_like_meta_skill_request(clean):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='meta_skill_request',
            domain='skill_factory',
            business_date=business_date,
            requires_root_owner=True,
        )
    if _looks_like_artifact_request(clean):
        return FactoryBrainIntent(
            intent_type='artifact_request',
            task_type='artifact_request',
            domain='artifact',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('本月经营', '月度经营', '月累计')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='monthly_operation',
            domain='operations',
            business_date=business_date,
        )
    if any(token in clean for token in ('年度经营', '年累计', '全年经营')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='yearly_operation',
            domain='operations',
            business_date=business_date,
        )
    if clean in {'产量', '今日产量', '今天产量'} or '日产量' in clean:
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='daily_output',
            domain='production',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('今天怎么样', '今天情况', '现在怎么样')):
        return FactoryBrainIntent(
            intent_type='contextual_intent',
            task_type='factory_overview',
            domain='operations',
            business_date=business_date,
        )
    if '日报' in clean:
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='daily_report',
            domain='production',
            business_date=business_date,
            requires_root_owner=True,
        )
    if any(token in clean for token in ('成品率', '成材率', '收得率')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='yield_analysis',
            domain='quality',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('是不是低了', '是不是高了')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='anomaly_analysis',
            domain='production',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if _looks_like_feedback_learning_request(clean):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='feedback_learning',
            domain='feedback',
            business_date=business_date,
        )
    if '为什么高' in clean or (
        '异常' in clean and not any(token in clean for token in ('能耗', '电耗', '气耗'))
    ):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='anomaly_analysis',
            domain='process_quality',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('合同余量', '余合同')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='contract_balance',
            domain='contract',
            business_date=business_date,
        )
    if any(token in clean for token in ('库存', '入库', '出库')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='inventory_query',
            domain='inventory',
            business_date=business_date,
        )
    if any(token in clean for token in ('能耗', '电耗', '气耗')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='energy_analysis',
            domain='energy',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('成本', '电费', '气费', '元/吨')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='cost_analysis',
            domain='cost',
            business_date=business_date,
        )
    if any(token in clean for token in ('合同', '发货', '交付')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='business_question',
            domain='operations',
            business_date=business_date,
        )
    if any(token in clean for token in ('笑话', '闲聊', '讲个')):
        return FactoryBrainIntent(
            intent_type='general_chat',
            task_type='general_chat',
            domain='general',
            business_date=None,
            should_use_factory_brain=False,
        )
    if clean in {'在干嘛', '你在干嘛'}:
        return FactoryBrainIntent(
            intent_type='general_chat',
            task_type='general_chat',
            domain='general',
            business_date=None,
            should_use_factory_brain=False,
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
        task_type='general_chat',
        domain='general',
        business_date=None,
        should_use_factory_brain=False,
    )


def _looks_like_long_term_rule(text: str) -> bool:
    return any(token in text for token in ('以后', '记住', '长期规则', '作为规则', '不要记住', '临时口径'))


def _looks_like_meta_skill_request(text: str) -> bool:
    if not any(token in text for token in ('skill', 'Skill', '技能', '技能包', 'agent', 'Agent', 'GitHub')):
        return False
    return any(
        token in text
        for token in ('生成', '创建', '做一个', '做个', '做一套', '帮我做', '搭一个', '方案', '规划', '设计', '参考')
    )


def _looks_like_artifact_request(text: str) -> bool:
    if not any(token in text for token in ('表格', 'Excel', '文档', 'PDF', '图表', '图片')):
        return False
    return any(
        token in text
        for token in ('生成', '导出', '整理', '汇总', '做成', '做个', '做一张', '给我', '发我', '出一份')
    )


def _looks_like_feedback_learning_request(text: str) -> bool:
    return any(
        token in text
        for token in ('我要反馈', '反馈一下', '我来反馈', '我要纠错', '我想纠错', '这个数据我想纠错', '你说错了', '你搞错了', '我要提意见')
    )


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

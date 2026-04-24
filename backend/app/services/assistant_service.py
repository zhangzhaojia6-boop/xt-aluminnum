from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from typing import Any
from urllib.parse import quote

import httpx

from app.adapters.llm import generate_llm_image_asset, generate_llm_summary
from app.config import Settings, settings as runtime_settings
from app.schemas.assistant import (
    AssistantCapabilitiesResponseOut,
    AssistantCapabilityGroupOut,
    AssistantCapabilityOut,
    AssistantImageRequestIn,
    AssistantImageResponseOut,
    AssistantIntegrationOut,
    AssistantLiveProbeResponseOut,
    AssistantQuickActionOut,
    AssistantQueryRequestIn,
    AssistantQueryResponseOut,
    AssistantResultCardOut,
    AssistantSummaryCardOut,
)

_DEFAULT_INTEGRATIONS_USED = ['dashboard', 'runtime_trace', 'delivery_status']
_QUERY_MODE_LABELS = {
    'answer': '问答',
    'search': '搜索',
    'retrieve': '检索',
    'generate_image': '图像生成',
    'automation': '自动化',
}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _llm_ready(runtime: Settings) -> bool:
    has_model_ref = _has_text(runtime.LLM_ENDPOINT_ID) or _has_text(runtime.LLM_MODEL)
    return bool(
        runtime.LLM_ENABLED
        and _has_text(runtime.LLM_API_BASE)
        and _has_text(runtime.LLM_API_KEY)
        and has_model_ref
    )


def _summary_model_ref(runtime: Settings) -> str:
    return str(runtime.LLM_ENDPOINT_ID or runtime.LLM_MODEL or '').strip()


def _image_model_ref(runtime: Settings) -> str:
    return str(runtime.LLM_IMAGE_ENDPOINT_ID or runtime.LLM_IMAGE_MODEL or _summary_model_ref(runtime)).strip()


def _parse_structured_json(raw_text: str) -> dict[str, Any] | None:
    text = str(raw_text or '').strip()
    if not text:
        return None

    if text.startswith('```'):
        parts = [segment.strip() for segment in text.split('```') if segment.strip()]
        if parts:
            candidate = parts[-1]
            if candidate.startswith('json'):
                candidate = candidate[4:].strip()
            text = candidate or text

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    if isinstance(parsed, dict):
        return parsed
    return None


def _normalize_cards(value: Any) -> list[AssistantResultCardOut]:
    if not isinstance(value, list):
        return []
    cards: list[AssistantResultCardOut] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or f'结果 {index + 1}').strip()
        summary = str(item.get('summary') or '').strip()
        if not title or not summary:
            continue

        source_labels_raw = item.get('source_labels')
        source_labels: list[str] = []
        if isinstance(source_labels_raw, list):
            for label in source_labels_raw:
                label_text = str(label or '').strip()
                if label_text:
                    source_labels.append(label_text)

        cards.append(
            AssistantResultCardOut(
                title=title[:28],
                summary=summary[:200],
                source_labels=source_labels[:4],
            )
        )
        if len(cards) >= 3:
            break
    return cards


def _normalize_actions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    actions: list[str] = []
    for item in value:
        action = str(item or '').strip()
        if action:
            actions.append(action[:40])
        if len(actions) >= 4:
            break
    return actions


def _normalize_integrations_used(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        entry = str(item or '').strip()
        if entry:
            normalized.append(entry[:40])
    return normalized[:6]


def _build_query_prompt(payload: AssistantQueryRequestIn) -> str:
    mode_label = _QUERY_MODE_LABELS.get(payload.mode, payload.mode)
    return (
        '请围绕“鑫泰铝业协同平台”生成结构化助手回复，严格输出 JSON：'
        '{"summary":"...","cards":[{"title":"...","summary":"...","source_labels":["..."]}],'
        '"next_actions":["..."],"integrations_used":["dashboard","runtime_trace","delivery_status"]}。\n'
        '要求：'
        'summary 20-80 字；cards 1-3 条；next_actions 1-4 条；'
        '不能编造具体业务数字，未知信息请用“需继续核实”。\n'
        f'当前模式：{mode_label}\n'
        f'用户问题：{payload.query}'
    )


def _build_mock_query_response(payload: AssistantQueryRequestIn) -> AssistantQueryResponseOut:
    return AssistantQueryResponseOut(
        mode=payload.mode,
        mock=True,
        summary='当前为 deterministic 回退，优先关注算法阻塞与交付闭环。',
        cards=[
            AssistantResultCardOut(
                title='阻塞优先级',
                summary='先处理缺报和退回，再清异常与交付缺口，可最快恢复全链路可靠度。',
                source_labels=['算法流水线', '执行交付助手'],
            )
        ],
        integrations_used=list(_DEFAULT_INTEGRATIONS_USED),
        next_actions=['查看阻塞清单', '触发交付检查', '生成简报卡'],
    )


def _build_image_svg(*, caption: str, badge_text: str) -> str:
    safe_caption = escape(caption or '今日产量、异常和交付风险简报图')
    safe_badge = escape(badge_text or 'deterministic mock')
    return f"""
<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='720' viewBox='0 0 1200 720'>
  <rect width='1200' height='720' rx='48' fill='#f7fbff'/>
  <path d='M130 188C274 88 430 96 574 180C704 256 818 278 1022 192' stroke='#0ea5e9' stroke-width='26' stroke-linecap='round' fill='none'/>
  <path d='M182 432C346 302 522 318 686 420C810 498 910 522 1052 456' stroke='#93c5fd' stroke-width='18' stroke-linecap='round' fill='none'/>
  <rect x='102' y='112' width='314' height='178' rx='28' fill='white' stroke='#dbeafe'/>
  <text x='136' y='170' font-size='28' fill='#0f172a'>鑫泰铝业 · 审阅简报</text>
  <text x='136' y='214' font-size='20' fill='#475569'>今日产量 / 异常 / 交付风险</text>
  <text x='136' y='258' font-size='32' fill='#0f172a'>{safe_badge}</text>
  <rect x='102' y='558' width='996' height='76' rx='18' fill='white' stroke='#dbeafe'/>
  <text x='136' y='606' font-size='24' fill='#334155'>{safe_caption}</text>
</svg>
""".strip()


def build_assistant_capabilities(*, settings: Settings | None = None) -> AssistantCapabilitiesResponseOut:
    runtime = settings or runtime_settings
    llm_enabled = _llm_ready(runtime)
    realtime_status = 'live' if llm_enabled else 'mock_ready'

    integrations = [
        AssistantIntegrationOut(key='dashboard', label='审阅首页', status=realtime_status),
        AssistantIntegrationOut(key='runtime_trace', label='流程追踪', status=realtime_status),
        AssistantIntegrationOut(key='delivery_status', label='交付状态', status=realtime_status),
    ]
    groups = [
        AssistantCapabilityGroupOut(
            key='analysis',
            kicker='分析决策',
            label='分析决策',
            description='聚焦异常归因、阻塞优先级和风险解释。',
            examples=['今天先处理哪个阻塞项', '哪里最影响交付'],
        ),
        AssistantCapabilityGroupOut(
            key='execution',
            kicker='执行交付',
            label='执行交付',
            description='围绕交付链路给出可执行动作与闭环建议。',
            examples=['现在能否发布日报', '交付缺口如何补齐'],
        ),
        AssistantCapabilityGroupOut(
            key='generate_image',
            kicker='图像输出',
            label='图像输出',
            description='生成简报图卡用于日报与管理看板。',
            examples=['生成今日简报图', '生成异常图卡'],
        ),
    ]
    return AssistantCapabilitiesResponseOut(
        connected=True,
        assistant_status='live' if llm_enabled else 'mock_ready',
        capabilities=[
            AssistantCapabilityOut(key='query', label='分析决策 / 执行交付', entrypoint='/api/v1/assistant/query'),
            AssistantCapabilityOut(key='generate_image', label='图像生成', entrypoint='/api/v1/assistant/generate-image'),
        ],
        integrations=integrations,
        quick_actions=[
            AssistantQuickActionOut(
                key='priority-blocker',
                label='阻塞优先级',
                mode='answer',
                query='今天先处理哪个阻塞项最有效？',
            ),
            AssistantQuickActionOut(
                key='delivery-readiness',
                label='交付就绪检查',
                mode='retrieve',
                query='当前交付链路还缺什么步骤？',
            ),
            AssistantQuickActionOut(
                key='daily-briefing-image',
                label='生成日报图',
                mode='generate_image',
                query='生成今日产量和异常简报图。',
            ),
        ],
        groups=groups,
        summary_cards=[
            AssistantSummaryCardOut(
                key='capabilities',
                title='能力域',
                value=str(len(groups)),
                detail='分析 / 执行 / 出图',
                tone='primary',
            ),
            AssistantSummaryCardOut(
                key='integrations',
                title='已接数据',
                value=str(len(integrations)),
                detail='首页 / 流程 / 交付',
                tone='neutral',
            ),
            AssistantSummaryCardOut(
                key='agents',
                title='双助手',
                value='在线',
                detail='分析决策 + 执行交付',
                tone='success',
            ),
        ],
    )


def run_assistant_query(
    payload: AssistantQueryRequestIn,
    *,
    settings: Settings | None = None,
    llm_client=None,
) -> AssistantQueryResponseOut:
    runtime = settings or runtime_settings
    fallback = _build_mock_query_response(payload)
    if not _llm_ready(runtime):
        return fallback

    try:
        llm_text = generate_llm_summary(
            messages=[
                {
                    'role': 'system',
                    'content': '你是工厂多智能体助手。你只能输出中文，并且不能编造未给出的事实。',
                },
                {
                    'role': 'user',
                    'content': _build_query_prompt(payload),
                },
            ],
            settings=runtime,
            client=llm_client,
        )
    except Exception:  # noqa: BLE001
        return fallback

    structured = _parse_structured_json(llm_text)
    if structured is None:
        summary_text = str(llm_text or '').strip()
        if not summary_text:
            return fallback
        return AssistantQueryResponseOut(
            mode=payload.mode,
            mock=False,
            summary=summary_text[:220],
            cards=fallback.cards,
            integrations_used=list(_DEFAULT_INTEGRATIONS_USED),
            next_actions=fallback.next_actions,
        )

    summary = str(structured.get('summary') or '').strip()
    cards = _normalize_cards(structured.get('cards'))
    next_actions = _normalize_actions(structured.get('next_actions'))
    integrations_used = _normalize_integrations_used(structured.get('integrations_used'))

    return AssistantQueryResponseOut(
        mode=payload.mode,
        mock=False,
        summary=summary or fallback.summary,
        cards=cards or fallback.cards,
        integrations_used=integrations_used or list(_DEFAULT_INTEGRATIONS_USED),
        next_actions=next_actions or fallback.next_actions,
    )


def build_assistant_image(
    payload: AssistantImageRequestIn,
    *,
    settings: Settings | None = None,
    llm_client=None,
) -> AssistantImageResponseOut:
    runtime = settings or runtime_settings
    is_mock = True
    caption = '今日产量、异常和交付风险简报图（mock）'
    next_actions = ['保存到日报卡片', '推送到审阅首页', '继续调用真实图像生成']
    badge_text = 'deterministic mock'
    image_url = ''

    if _llm_ready(runtime):
        try:
            asset = generate_llm_image_asset(
                prompt=payload.prompt,
                settings=runtime,
                client=llm_client,
            )
            image_url = str(asset.get('image_url') or '').strip()
            if image_url:
                is_mock = False
                badge_text = str(asset.get('model') or runtime.LLM_MODEL or runtime.LLM_ENDPOINT_ID or 'DeepSeek-V3.2').strip()[:40] or 'DeepSeek-V3.2'
        except Exception:  # noqa: BLE001
            image_url = ''

        try:
            llm_text = generate_llm_summary(
                messages=[
                    {
                        'role': 'system',
                        'content': '你是工厂日报图卡助手。请输出 JSON，不要输出额外解释。',
                    },
                    {
                        'role': 'user',
                        'content': (
                            '请根据用户需求生成 JSON：'
                            '{"caption":"20-48字中文标题","next_actions":["动作1","动作2","动作3"]}。'
                            f'用户需求：{payload.prompt}'
                        ),
                    },
                ],
                settings=runtime,
                client=llm_client,
            )
            structured = _parse_structured_json(llm_text)
            if structured is not None:
                caption_candidate = str(structured.get('caption') or '').strip()
                actions_candidate = _normalize_actions(structured.get('next_actions'))
                if caption_candidate:
                    caption = caption_candidate[:48]
                if actions_candidate:
                    next_actions = actions_candidate
            else:
                caption_candidate = str(llm_text or '').strip()
                if caption_candidate:
                    caption = caption_candidate[:48]

        except Exception:  # noqa: BLE001
            pass

    if image_url:
        return AssistantImageResponseOut(
            mock=False,
            image_type='daily_briefing_card',
            asset_id='daily-briefing-card-llm',
            image_url=image_url,
            suggested_caption=caption,
            next_actions=next_actions,
        )

    svg = _build_image_svg(caption=caption, badge_text=badge_text)
    return AssistantImageResponseOut(
        mock=is_mock,
        image_type='daily_briefing_card',
        asset_id='daily-briefing-card-llm' if not is_mock else 'mock-daily-briefing-card',
        image_url=f'data:image/svg+xml;utf8,{quote(svg)}',
        suggested_caption=caption,
        next_actions=next_actions,
    )


def run_assistant_live_probe(
    *,
    settings: Settings | None = None,
    llm_client=None,
) -> AssistantLiveProbeResponseOut:
    runtime = settings or runtime_settings
    errors: list[str] = []
    ready = _llm_ready(runtime)
    text_probe_ok = False
    image_probe_ok = False
    text_model = _summary_model_ref(runtime)
    image_model = _image_model_ref(runtime)

    if not ready:
        errors.append('LLM runtime not ready: check LLM_ENABLED, LLM_API_BASE, LLM_API_KEY and model reference')
        return AssistantLiveProbeResponseOut(
            ready=False,
            text_probe_ok=False,
            image_probe_ok=False,
            overall_ok=False,
            text_model=text_model,
            image_model=image_model,
            checked_at=datetime.now(timezone.utc).isoformat(),
            errors=errors,
        )

    probe_client = llm_client
    created_probe_client = None
    if probe_client is None:
        created_probe_client = httpx.Client(timeout=max(float(runtime.LLM_TIMEOUT_SECONDS), 60.0))
        probe_client = created_probe_client

    try:
        try:
            summary = generate_llm_summary(
                messages=[
                    {'role': 'system', 'content': '你是工厂系统连通性探针，只返回一行短句。'},
                    {'role': 'user', 'content': '返回“live-probe-ok”。'},
                ],
                settings=runtime,
                client=probe_client,
            )
            text_probe_ok = bool(str(summary or '').strip())
        except Exception as exc:  # noqa: BLE001
            errors.append(f'text probe failed: {exc}')

        try:
            image_asset = generate_llm_image_asset(
                prompt='生成一张用于工厂日报封面的抽象图卡，蓝白主色，避免文字。',
                settings=runtime,
                client=probe_client,
            )
            image_url = str(image_asset.get('image_url') or '').strip()
            image_probe_ok = bool(image_url) and not image_url.startswith('data:image/svg+xml;utf8,')
        except Exception as exc:  # noqa: BLE001
            errors.append(f'image probe failed: {exc}')
    finally:
        if created_probe_client is not None:
            created_probe_client.close()

    return AssistantLiveProbeResponseOut(
        ready=True,
        text_probe_ok=text_probe_ok,
        image_probe_ok=image_probe_ok,
        overall_ok=text_probe_ok and image_probe_ok,
        text_model=text_model,
        image_model=image_model,
        checked_at=datetime.now(timezone.utc).isoformat(),
        errors=errors,
    )

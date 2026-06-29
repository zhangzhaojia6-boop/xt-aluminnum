from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    entry_id: str
    title: str
    category: str
    content: str
    source_ref: str
    tags: tuple[str, ...]


DEFAULT_ENTRIES: tuple[KnowledgeEntry, ...] = (
    KnowledgeEntry(
        entry_id='metric_factory_output',
        title='全厂总产量与车间产量口径',
        category='metric_rule',
        content=(
            '全厂总产量按最后入库/包装入库口径看，不把各车间下机量简单相加。'
            '车间产量用于观察本车间过站、下机或道次情况，是参考口径，不能直接当全厂总产量。'
        ),
        source_ref='docs/superpowers/plans/2026-06-12-stitch-image2-phase9-metric-contract-check.md',
        tags=('全厂总产量', '车间产量', '包装产量', '入库产量', '下机量', '最后入库'),
    ),
    KnowledgeEntry(
        entry_id='mes_manual_fill_boundary',
        title='MES 主数据与人工填报边界',
        category='data_source_rule',
        content=(
            '生产、在制、卷材、工艺和包装产量优先使用外部 MES 数据经过数据中枢整理后的结果。'
            '人工填报用于补录、纠偏、异常说明和 MES 缺字段补充，不能反向覆盖 MES 主口径。'
        ),
        source_ref='docs/superpowers/plans/2026-06-09-mes-fill-report-optimization-route.md',
        tags=('MES', '人工填报', '补录', '对照', '纠偏', '主数据', '冲突'),
    ),
    KnowledgeEntry(
        entry_id='business_day_boundary',
        title='业务日时间口径',
        category='time_rule',
        content=(
            '日报、今日、调度和 MES 在制数据必须使用同一套业务时间口径，不能自然日和业务日混用。'
            '生产经营日报按业务日汇总，页面需要标明数据来源和统计区间。'
        ),
        source_ref='docs/superpowers/plans/2026-06-09-mes-fill-report-optimization-route.md',
        tags=('业务日', '统计区间', '日报', '今日', '调度', 'MES在制'),
    ),
    KnowledgeEntry(
        entry_id='daily_report_publish_rule',
        title='日报发布与口径说明',
        category='daily_report_rule',
        content=(
            '日报正文必须先按数据中枢的确定性口径生成，再进入预览和确认。'
            '发布内容要说明生产主数据、人工补录、算法指标各自来源，不能用 AI 临时编数字。'
        ),
        source_ref='docs/superpowers/plans/2026-06-13-dingtalk-stage7-implementation-report.md',
        tags=('日报', '发布日报', '预览', '确认', '数据来源', 'AI编数'),
    ),
    KnowledgeEntry(
        entry_id='mes_field_contract',
        title='MES 字段在数据中枢的用途',
        category='mes_field_rule',
        content=(
            '随行卡号用于串起卷材流转；客户、合金、规格用于识别订单和产品属性；'
            '工艺路线说明卷材应该经过哪些工序，当前工艺用于判断卷材现在处在哪个环节。'
            '设备名或 PC 需要通过机列映射后才能落到责任机列，不能只看 PC 字样就认定机台。'
        ),
        source_ref='docs/superpowers/specs/2026-06-10-mes-triggered-mobile-supplement-design.md',
        tags=('MES', '随行卡', '客户', '合金', '规格', '工艺路线', '当前工艺', '设备', 'PC', '机列'),
    ),
    KnowledgeEntry(
        entry_id='active_workshop_scope',
        title='车间范围和车间群口径',
        category='workshop_rule',
        content=(
            '车间汇报按当前生产组织范围拆分，管理层看全厂，车间群只看本车间。'
            '车间名称、别名和机列映射必须先在数据中枢统一后再展示，避免同一车间拆成多套口径。'
        ),
        source_ref='docs/superpowers/plans/2026-06-13-dingtalk-multimodal-active-agent-reporting-plan.md',
        tags=('车间', '车间群', '管理群', '别名', '机列映射', '权限范围'),
    ),
    KnowledgeEntry(
        entry_id='anomaly_review_flow',
        title='异常检测处理规则',
        category='anomaly_rule',
        content=(
            '异常检测发现 MES 和填报不一致时，先生成待核查事项，保留两边来源和值。'
            '图片、语音、OCR 和人工说明只能辅助判断，人工确认前不能直接改正式指标。'
            '确认后再进入纠偏或关闭流程。'
        ),
        source_ref='docs/superpowers/plans/2026-06-13-dingtalk-stage2-implementation-report.md',
        tags=('异常检测', 'MES', '填报', '待核查', '人工确认', '纠偏', '正式指标'),
    ),
    KnowledgeEntry(
        entry_id='mobile_fill_supplement_rule',
        title='填报端补录规则',
        category='fill_rule',
        content=(
            '填报端用于补录 MES 缺字段、异常说明和现场确认信息。'
            '有 MES 主数据时，前端展示 MES 参考值和人工填报值；人工填报不能直接覆盖 MES 主数据。'
        ),
        source_ref='docs/superpowers/plans/2026-06-09-mes-assisted-fill-simplification.md',
        tags=('填报端', '补录', 'MES参考值', '人工填报值', '异常说明', '现场确认'),
    ),
    KnowledgeEntry(
        entry_id='multimodal_evidence_boundary',
        title='图片语音证据边界',
        category='evidence_rule',
        content=(
            '图片、语音、附件和 OCR 结果只能作为证据留档。'
            '机器识别结果在人工确认前不能进入正式产量、能耗或日报指标。'
        ),
        source_ref='docs/superpowers/plans/2026-06-13-dingtalk-stage3-implementation-report.md',
        tags=('图片', '语音', '附件', 'OCR', '证据', '人工确认', '正式指标'),
    ),
    KnowledgeEntry(
        entry_id='operation_approval_boundary',
        title='补产量和发布日报审批规则',
        category='approval_rule',
        content=(
            '补产量和发布日报必须限制为指定人员操作。'
            '流程必须先生成预览，再二次确认，未确认不能执行；默认 dry-run，不直接写正式数据。'
        ),
        source_ref='docs/superpowers/plans/2026-06-13-dingtalk-stage4-implementation-report.md',
        tags=('补产量', '发布日报', '白名单', '预览', '二次确认', 'dry-run', '审批'),
    ),
    KnowledgeEntry(
        entry_id='channel_permission_boundary',
        title='钉钉群和车间权限边界',
        category='permission_rule',
        content=(
            '管理群接收全厂总览，车间群只接收本车间汇报。'
            '未绑定权限范围的群不能接收生产敏感数据，同一异常需要限频，避免刷屏。'
        ),
        source_ref='docs/superpowers/plans/2026-06-13-dingtalk-stage2-implementation-report.md',
        tags=('管理群', '车间群', '权限', '敏感数据', '限频', '异常'),
    ),
)

REALTIME_WORDS = ('今天', '现在', '实时', '当前', '此刻', '刚才')
METRIC_WORDS = ('产量', '能耗', '缺报', '在制', '合同量', '成品率', '日报', '库存', '异常')


def answer_question(question: str, *, entries: tuple[KnowledgeEntry, ...] = DEFAULT_ENTRIES) -> dict:
    clean_question = str(question or '').strip()
    if _is_realtime_metric_question(clean_question):
        return {
            'can_answer': False,
            'confidence': 'blocked_realtime',
            'answer': '知识库只能解释口径，不能提供实时数值。请查询实时接口或管理端页面。',
            'citations': [],
            'missing_data': ['实时接口'],
            'recommended_next_actions': ['打开管理端实时页面', '查询对应后端接口'],
        }

    matched = _search_entries(clean_question, entries=entries)
    if not matched:
        return {
            'can_answer': False,
            'confidence': 'low',
            'answer': '没有找到足够资料，不能可靠回答这个问题。',
            'citations': [],
            'missing_data': ['知识库资料不足'],
            'recommended_next_actions': ['补充口径文档', '转人工确认'],
        }

    selected = [entry for entry, _score in matched[:3]]
    answer_text = ' '.join(entry.content for entry in selected)
    return {
        'can_answer': True,
        'confidence': 'high' if matched[0][1] >= 3 else 'medium',
        'answer': answer_text,
        'citations': [_citation(entry) for entry in selected],
        'missing_data': [],
        'recommended_next_actions': ['查看来源文档', '如需实时数值请打开管理端页面'],
    }


def build_grounded_prompt(question: str, answer: dict) -> str:
    source_lines = []
    for index, citation in enumerate(answer.get('citations') or [], start=1):
        source_lines.append(
            f"来源 {index}: {citation.get('entry_id')} | {citation.get('title')} | {citation.get('source_ref')}"
        )
    source_block = '\n'.join(source_lines) if source_lines else '来源：无'
    return (
        '你是鑫泰铝业智能大脑。'
        '只允许根据这些来源回答；不能编造实时产量、能耗、合同量、成品率或人员信息。'
        '如果来源不足，必须说资料不足。'
        f'\n问题：{question}'
        f'\n{source_block}'
        f'\n草稿回答：{answer.get("answer", "")}'
    )


def list_knowledge_entries() -> list[dict]:
    return [
        {
            'entry_id': entry.entry_id,
            'title': entry.title,
            'category': entry.category,
            'source_ref': entry.source_ref,
            'tags': list(entry.tags),
        }
        for entry in DEFAULT_ENTRIES
    ]


def _search_entries(question: str, *, entries: tuple[KnowledgeEntry, ...]) -> list[tuple[KnowledgeEntry, int]]:
    scored: list[tuple[KnowledgeEntry, int]] = []
    for entry in entries:
        score = _score_entry(question, entry)
        if score > 0:
            scored.append((entry, score))
    scored.sort(key=lambda item: (-item[1], item[0].entry_id))
    return scored


def _score_entry(question: str, entry: KnowledgeEntry) -> int:
    score = 0
    haystacks = (entry.title, entry.category, entry.content, *entry.tags)
    for text in haystacks:
        clean_text = str(text)
        if clean_text and clean_text in question:
            score += 3
    for tag in entry.tags:
        if tag and str(tag).lower() in question.lower():
            score += 2
    for keyword in _split_keywords(question):
        if len(keyword) >= 2 and any(keyword in str(text) for text in haystacks):
            score += 1
    return score


def _split_keywords(question: str) -> list[str]:
    separators = ' ，,。？?：:；;、/\\|+-_()（）'
    text = question
    for sep in separators:
        text = text.replace(sep, ' ')
    return [item.strip() for item in text.split() if item.strip()]


def _is_realtime_metric_question(question: str) -> bool:
    return any(word in question for word in REALTIME_WORDS) and any(word in question for word in METRIC_WORDS)


def _citation(entry: KnowledgeEntry) -> dict:
    return {
        'entry_id': entry.entry_id,
        'title': entry.title,
        'source_ref': entry.source_ref,
    }

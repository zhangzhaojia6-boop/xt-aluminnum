# Daily Report Agent Workflow and Workshop Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 7:30 initial daily report, 9:35 correction report, six-Agent SOP, RAG knowledge bootstrap, MES/system data dictionary, and all-workshop report cards for 鑫泰铝业 数据中枢.

**Architecture:** Keep existing report generation and outbox infrastructure. Add focused services that assemble workshop cards, compare report versions, bootstrap RAG/SOP knowledge, and queue DingTalk robot messages through `agent_outbox`; do not let Agent code call DingTalk directly. Store version/card metadata inside `DailyReport.report_data` first to avoid schema churn unless tests prove a dedicated table is required.

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, pytest, Vue 3, existing RAG service, existing DingTalk custom robot channel support, existing template daily report services.

## Global Constraints

- Product name is `鑫泰铝业 数据中枢`; do not call the product a MES system.
- MES SQL Server is read-only; never write to the MES source database.
- Frontend never connects to MES SQL Server directly.
- Do not commit database passwords, DingTalk webhook/secret, LLM keys, access tokens, or connection strings.
- RAG stores rules, templates, dictionaries, and explanations; RAG must not store daily dynamic production numbers as truth.
- All DingTalk outbound messages must go through `agent_outbox` and `external_message_logs`.
- 7:30 initial report must send every day.
- 9:35 correction report sends only when key fields changed after manual supplement.
- Every daily report includes all workshop cards.
- Missing data displays `/` and is recorded as a gap; missing data must not block 7:30 initial sending.
- 人工补录 can change the report, but changes must be versioned and summarized.
- Keep changes surgical; do not delete old routes, old report pages, `/entry`, `/manage`, DingTalk H5, existing report generation, reminders, realtime stream, permissions, audit, or history-compatible routes.

---

## File Structure

Create:

- `backend/app/services/agent_sop_bootstrap_service.py`  
  Owns six-Agent SOP payloads and updates `AgentProfile.config_payload`.
- `backend/scripts/bootstrap_agent_sop.py`  
  Safe preview/apply script for SOP bootstrap.
- `backend/app/services/rag_bootstrap_service.py`  
  Imports stable text knowledge from output-skill files and generated dictionaries.
- `backend/scripts/bootstrap_rag_knowledge.py`  
  Safe preview/apply script for RAG bootstrap.
- `backend/app/services/mes_data_dictionary_service.py`  
  Reads local projected MES models and optional SQL Server metadata to produce sanitized dictionaries.
- `backend/app/services/report/workshop_daily_cards.py`  
  Builds all workshop cards from MES projection, system facts, energy facts, and manual supplements.
- `backend/app/services/report/daily_report_versions.py`  
  Stores initial/correction/final metadata in `DailyReport.report_data` and computes key-field diffs.
- `backend/app/services/report/daily_report_agent_delivery.py`  
  Queues initial/correction report messages to the daily report secretary robot through outbox.
- `backend/tests/test_agent_sop_bootstrap_service.py`
- `backend/tests/test_rag_bootstrap_service.py`
- `backend/tests/test_mes_data_dictionary_service.py`
- `backend/tests/test_workshop_daily_cards.py`
- `backend/tests/test_daily_report_versions.py`
- `backend/tests/test_daily_report_agent_delivery.py`

Modify:

- `backend/app/services/agent_personal_bootstrap_service.py`  
  Include SOP keys while preserving existing capabilities.
- `backend/app/core/scheduler.py`  
  Add `daily_report_initial_0730` and `daily_report_correction_0935` jobs.
- `backend/app/tasks/daily_report.py`  
  Split current `generate_daily_reports` into explicit initial/correction task functions.
- `backend/app/services/report/template_daily_report.py`  
  Append workshop cards to report payload and expose source/gap metadata.
- `backend/app/services/agent_management_overview_service.py`  
  Surface SOP completeness, RAG document counts, and report delivery state.
- `frontend/src/views/manage/admin/AgentManagementPage.vue`  
  Show Agent SOP status and report workflow status without changing routes.
- `frontend/src/views/manage/rag/RagKnowledgePage.vue`  
  Show imported knowledge categories and counts.
- `frontend/src/views/manage/channels/CommunicationChannelsPage.vue`  
  Ensure custom robot type label displays as 钉钉机器人.

Do not modify unless a task explicitly says so:

- `backend/app/models/reports.py`
- `backend/app/models/agent_communication.py`
- Alembic migrations

The first implementation pass should avoid migrations by using existing JSON payloads.

---

### Task 1: Six-Agent SOP Bootstrap

**Files:**
- Create: `backend/app/services/agent_sop_bootstrap_service.py`
- Create: `backend/scripts/bootstrap_agent_sop.py`
- Test: `backend/tests/test_agent_sop_bootstrap_service.py`
- Modify: `backend/app/services/agent_personal_bootstrap_service.py`

**Interfaces:**
- Consumes: `AgentProfile`, existing `_zzj` agent codes.
- Produces: `build_zzj_agent_sop_plan() -> dict`, `ensure_zzj_agent_sop(db: Session, apply: bool = False) -> AgentSopBootstrapOutcome`.

- [ ] **Step 1: Write failing SOP bootstrap tests**

Create `backend/tests/test_agent_sop_bootstrap_service.py`:

```python
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentProfile
from app.services.agent_personal_bootstrap_service import ensure_zhang_zhaojia_personal_agents
from app.services.agent_sop_bootstrap_service import ensure_zzj_agent_sop


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_sop_preview_does_not_write() -> None:
    db = _session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        outcome = ensure_zzj_agent_sop(db, apply=False)

        assert outcome.applied is False
        assert outcome.agent_total == 6
        assert outcome.workflow_total >= 6
        agent = db.query(AgentProfile).filter(AgentProfile.code == 'daily_report_secretary_zzj').one()
        assert 'workflow' not in (agent.config_payload or {})
    finally:
        db.close()


def test_sop_apply_adds_workflows_without_removing_capabilities() -> None:
    db = _session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        outcome = ensure_zzj_agent_sop(db, apply=True)

        assert outcome.applied is True
        secretary = db.query(AgentProfile).filter(AgentProfile.code == 'daily_report_secretary_zzj').one()
        payload = secretary.config_payload or {}
        assert payload['capabilities'] == ['daily_report_preview', 'report_publish_approval_required']
        assert payload['workflow']['initial_report_time'] == '07:30'
        assert payload['workflow']['correction_report_time'] == '09:35'
        assert payload['workflow']['requires_outbox'] is True
        assert payload['workflow']['can_direct_send_dingtalk'] is False
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest -q tests/test_agent_sop_bootstrap_service.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.agent_sop_bootstrap_service'`.

- [ ] **Step 3: Implement SOP bootstrap service**

Create `backend/app/services/agent_sop_bootstrap_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentProfile


ZZJ_AGENT_WORKFLOWS: dict[str, dict[str, Any]] = {
    'factory_dispatch_zzj': {
        'role': '全厂调度 Agent',
        'daily_triggers': ['07:30_initial_report', '09:35_correction_check'],
        'responsibilities': ['factory_overview', 'mes_sync_status', 'major_alerts'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'fill_gap_guard_zzj': {
        'role': '填报对账 Agent',
        'daily_triggers': ['07:30_gap_scan', '09:35_manual_supplement_diff'],
        'responsibilities': ['missing_fields', 'unmatched_machine', 'manual_vs_mes_diff'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'energy_guard_zzj': {
        'role': '能耗守卫 Agent',
        'daily_triggers': ['07:30_energy_snapshot', '09:35_energy_recalc'],
        'responsibilities': ['electricity', 'gas', 'energy_per_ton_by_packaging_output'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'quality_guard_zzj': {
        'role': '质量异常 Agent',
        'daily_triggers': ['07:30_quality_gate', '09:35_quality_recheck'],
        'responsibilities': ['quality_gate', 'open_quality_issues', 'blocking_summary'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'daily_report_secretary_zzj': {
        'role': '日报秘书 Agent',
        'initial_report_time': '07:30',
        'correction_report_time': '09:35',
        'daily_triggers': ['07:30_initial_report_send', '09:35_correction_report_send_if_changed'],
        'responsibilities': ['render_factory_report', 'render_workshop_cards', 'queue_outbox'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
        'requires_final_confirmation': True,
    },
    'governance_auditor_zzj': {
        'role': '治理留档 Agent',
        'daily_triggers': ['after_initial_report', 'after_correction_report'],
        'responsibilities': ['outbox_audit', 'external_message_logs', 'version_diff_archive'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
}


@dataclass(frozen=True, slots=True)
class AgentSopBootstrapOutcome:
    applied: bool
    agent_total: int
    workflow_total: int
    agent_codes: list[str]


def build_zzj_agent_sop_plan() -> dict[str, Any]:
    return {
        'agent_codes': list(ZZJ_AGENT_WORKFLOWS),
        'workflows': ZZJ_AGENT_WORKFLOWS,
        'safety': {
            'requires_outbox': True,
            'direct_dingtalk_send_allowed': False,
            'stores_secrets': False,
        },
    }


def ensure_zzj_agent_sop(db: Session, *, apply: bool = False) -> AgentSopBootstrapOutcome:
    codes = list(ZZJ_AGENT_WORKFLOWS)
    agents = db.query(AgentProfile).filter(AgentProfile.code.in_(codes)).all()
    if apply:
        by_code = {agent.code: agent for agent in agents}
        for code, workflow in ZZJ_AGENT_WORKFLOWS.items():
            agent = by_code.get(code)
            if agent is None:
                continue
            payload = dict(agent.config_payload or {})
            payload['workflow'] = workflow
            payload['sop_version'] = '2026-06-18'
            agent.config_payload = payload
        db.flush()
    return AgentSopBootstrapOutcome(
        applied=bool(apply),
        agent_total=len(agents),
        workflow_total=len(ZZJ_AGENT_WORKFLOWS),
        agent_codes=codes,
    )
```

- [ ] **Step 4: Add preview/apply script**

Create `backend/scripts/bootstrap_agent_sop.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.agent_sop_bootstrap_service import build_zzj_agent_sop_plan, ensure_zzj_agent_sop


def main() -> int:
    parser = argparse.ArgumentParser(description='配置张兆嘉六个 Agent 的 SOP 工作流')
    parser.add_argument('--apply', action='store_true', help='写入数据库；默认只预览')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({**build_zzj_agent_sop_plan(), 'applied': False}, ensure_ascii=False, indent=2))
        return 0
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        outcome = ensure_zzj_agent_sop(db, apply=True)
        db.commit()
    print(json.dumps(outcome.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 5: Run SOP tests**

Run:

```bash
cd backend
pytest -q tests/test_agent_sop_bootstrap_service.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent_sop_bootstrap_service.py backend/scripts/bootstrap_agent_sop.py backend/tests/test_agent_sop_bootstrap_service.py
git commit -m "feat: define zzj agent sop workflows"
```

---

### Task 2: RAG Knowledge Bootstrap from Output Skill and Dictionaries

**Files:**
- Create: `backend/app/services/rag_bootstrap_service.py`
- Create: `backend/scripts/bootstrap_rag_knowledge.py`
- Test: `backend/tests/test_rag_bootstrap_service.py`

**Interfaces:**
- Consumes: `create_document_from_bytes()`.
- Produces: `build_rag_bootstrap_manifest(reference_root: Path) -> list[RagBootstrapItem]`, `bootstrap_rag_knowledge(db, reference_root: Path, apply: bool = False) -> RagBootstrapOutcome`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_rag_bootstrap_service.py`:

```python
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.rag import RagDocument
from app.services.rag_bootstrap_service import bootstrap_rag_knowledge


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_bootstrap_rag_preview_does_not_write(tmp_path: Path) -> None:
    (tmp_path / '2026-6-16_日报正文.txt').write_text('6月16日，车间总产量日合计328吨。', encoding='utf-8')
    (tmp_path / '2026-6-16_核对记录.txt').write_text('报告日：2026-06-16\\n母版口径：按正文保留段落。', encoding='utf-8')
    db = _session()
    try:
        outcome = bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=False)
        assert outcome.applied is False
        assert outcome.document_total == 2
        assert db.query(RagDocument).count() == 0
    finally:
        db.close()


def test_bootstrap_rag_apply_imports_output_skill_as_rule_docs(tmp_path: Path) -> None:
    (tmp_path / '2026-6-16_日报正文.txt').write_text('6月16日，车间总产量日合计328吨。', encoding='utf-8')
    (tmp_path / '2026-6-16_核对记录.txt').write_text('报告日：2026-06-16\\n母版口径：按正文保留段落。', encoding='utf-8')
    db = _session()
    try:
        outcome = bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)
        assert outcome.applied is True
        assert outcome.document_total == 2
        docs = db.query(RagDocument).order_by(RagDocument.filename.asc()).all()
        assert [doc.metadata_payload['category'] for doc in docs] == ['daily_report_rule', 'daily_report_rule']
        assert all(doc.status == 'active' for doc in docs)
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest -q tests/test_rag_bootstrap_service.py
```

Expected: FAIL because `rag_bootstrap_service` does not exist.

- [ ] **Step 3: Implement RAG bootstrap service**

Create `backend/app/services/rag_bootstrap_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.rag import RagDocument
from app.services.rag_service import create_document_from_bytes


@dataclass(frozen=True, slots=True)
class RagBootstrapItem:
    path: Path
    category: str
    source_name: str


@dataclass(frozen=True, slots=True)
class RagBootstrapOutcome:
    applied: bool
    document_total: int
    filenames: list[str]


def build_rag_bootstrap_manifest(reference_root: Path) -> list[RagBootstrapItem]:
    root = Path(reference_root)
    items: list[RagBootstrapItem] = []
    for path in sorted(root.glob('*_日报正文.txt')):
        items.append(RagBootstrapItem(path=path, category='daily_report_rule', source_name='输出skill日报正文样例'))
    for path in sorted(root.glob('*_核对记录.txt')):
        items.append(RagBootstrapItem(path=path, category='daily_report_rule', source_name='输出skill日报核对记录'))
    return items


def bootstrap_rag_knowledge(db: Session, *, reference_root: Path, apply: bool = False) -> RagBootstrapOutcome:
    items = build_rag_bootstrap_manifest(reference_root)
    if apply:
        existing = {
            name
            for (name,) in db.query(RagDocument.filename).all()
        }
        for item in items:
            if item.path.name in existing:
                continue
            create_document_from_bytes(
                db,
                filename=item.path.name,
                content=item.path.read_bytes(),
                content_type='text/plain',
                uploaded_by=None,
                source_name=item.source_name,
                metadata={'category': item.category, 'reference_root': str(reference_root)},
                scope={'permission_scope': 'factory'},
            )
        db.flush()
    return RagBootstrapOutcome(
        applied=bool(apply),
        document_total=len(items),
        filenames=[item.path.name for item in items],
    )
```

- [ ] **Step 4: Add bootstrap script**

Create `backend/scripts/bootstrap_rag_knowledge.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.rag_bootstrap_service import bootstrap_rag_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description='导入稳定 RAG 知识库资料')
    parser.add_argument('--reference-root', default='D:/输出skill')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(args.reference_root)
    if not root.exists():
        print(json.dumps({'applied': False, 'error': 'reference_root_not_found', 'reference_root': str(root)}, ensure_ascii=False, indent=2))
        return 2
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        outcome = bootstrap_rag_knowledge(db, reference_root=root, apply=args.apply)
        if args.apply:
            db.commit()
    print(json.dumps(outcome.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 5: Run RAG tests**

```bash
cd backend
pytest -q tests/test_rag_bootstrap_service.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/rag_bootstrap_service.py backend/scripts/bootstrap_rag_knowledge.py backend/tests/test_rag_bootstrap_service.py
git commit -m "feat: bootstrap output skill rag knowledge"
```

---

### Task 3: Sanitized MES and System Data Dictionary

**Files:**
- Create: `backend/app/services/mes_data_dictionary_service.py`
- Test: `backend/tests/test_mes_data_dictionary_service.py`

**Interfaces:**
- Produces: `build_projected_mes_dictionary() -> dict`, `render_dictionary_markdown(payload: dict) -> str`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_mes_data_dictionary_service.py`:

```python
from __future__ import annotations

from app.services.mes_data_dictionary_service import build_projected_mes_dictionary, render_dictionary_markdown


def test_mes_dictionary_contains_known_projection_tables_without_secrets() -> None:
    payload = build_projected_mes_dictionary()
    text = render_dictionary_markdown(payload)

    assert 'mes_workshop_process_records' in text
    assert 'mes_material_records' in text
    assert 'output_weight_tons' in text
    assert 'password' not in text.lower()
    forbidden_terms = ['数据库' + '密码', '数据库' + '账号', '数据库' + '地址', '连接串']
    for forbidden in forbidden_terms:
        assert forbidden not in text


def test_mes_dictionary_explains_report_usage() -> None:
    payload = build_projected_mes_dictionary()
    tables = {table['table_name']: table for table in payload['tables']}

    assert tables['mes_workshop_process_records']['report_usage'] == '工序产量、包装产量、车间分项日报卡'
    assert tables['mes_material_records']['report_usage'] == '热轧、铸二、铸三坯料卷产量参考'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest -q tests/test_mes_data_dictionary_service.py
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement sanitized dictionary service**

Create `backend/app/services/mes_data_dictionary_service.py`:

```python
from __future__ import annotations

from app.models.mes import MesMaterialRecord, MesWipTotalSnapshot, MesWorkshopProcessRecord


MODEL_USAGE = {
    MesWorkshopProcessRecord.__tablename__: '工序产量、包装产量、车间分项日报卡',
    MesMaterialRecord.__tablename__: '热轧、铸二、铸三坯料卷产量参考',
    MesWipTotalSnapshot.__tablename__: '在制料和在制卷分布',
}


def build_projected_mes_dictionary() -> dict:
    tables = []
    for model in (MesWorkshopProcessRecord, MesMaterialRecord, MesWipTotalSnapshot):
        table = model.__table__
        tables.append({
            'table_name': table.name,
            'report_usage': MODEL_USAGE[table.name],
            'columns': [
                {
                    'name': column.name,
                    'type': str(column.type),
                    'nullable': bool(column.nullable),
                    'is_time_field': column.name.endswith('_at') or 'date' in column.name,
                    'is_weight_field': 'weight' in column.name or column.name.endswith('_tons'),
                }
                for column in table.columns
            ],
        })
    return {'source': 'data_hub_mes_projection_models', 'tables': tables}


def render_dictionary_markdown(payload: dict) -> str:
    lines = ['# MES 投影数据字典', '', '说明：本文档不包含数据库地址、账号、密码或密钥。', '']
    for table in payload.get('tables') or []:
        lines.append(f"## {table['table_name']}")
        lines.append(f"用途：{table['report_usage']}")
        lines.append('')
        for column in table.get('columns') or []:
            flags = []
            if column.get('is_time_field'):
                flags.append('时间字段')
            if column.get('is_weight_field'):
                flags.append('重量字段')
            suffix = f"（{'、'.join(flags)}）" if flags else ''
            lines.append(f"- {column['name']}: {column['type']}{suffix}")
        lines.append('')
    return '\n'.join(lines).strip() + '\n'
```

- [ ] **Step 4: Run dictionary tests**

```bash
cd backend
pytest -q tests/test_mes_data_dictionary_service.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/mes_data_dictionary_service.py backend/tests/test_mes_data_dictionary_service.py
git commit -m "feat: add sanitized mes dictionary"
```

---

### Task 4: Workshop Daily Cards

**Files:**
- Create: `backend/app/services/report/workshop_daily_cards.py`
- Test: `backend/tests/test_workshop_daily_cards.py`
- Modify: `backend/app/services/report/template_daily_report.py`

**Interfaces:**
- Produces: `build_workshop_daily_cards(db: Session, target_date: date) -> dict`, `render_workshop_cards(cards_payload: dict) -> str`.
- `template_daily_report.build_template_daily_report_payload()` includes `workshop_cards` and appends rendered cards to `text`.

- [ ] **Step 1: Write failing tests for park shearing and all-workshop skeleton**

Create `backend/tests/test_workshop_daily_cards.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.master import Workshop
from app.models.mes import MesWorkshopProcessRecord
from app.services.report.workshop_daily_cards import build_workshop_daily_cards, render_workshop_cards


REPORT_DATE = date(2026, 6, 16)


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_park_shearing_card_uses_packaging_output_as_energy_denominator() -> None:
    db = _session()
    try:
        db.add(Workshop(id=1, code='PARK_SHEAR', name='园区剪切', workshop_type='shearing', is_active=True))
        db.add_all([
            MesWorkshopProcessRecord(business_date=REPORT_DATE, workshop_name='园区剪切', process_name='飞剪', output_weight_tons=74.17, source_id='fj-1'),
            MesWorkshopProcessRecord(business_date=REPORT_DATE, workshop_name='园区剪切', process_name='重卷', output_weight_tons=12.685, source_id='zj-1'),
            MesWorkshopProcessRecord(business_date=REPORT_DATE, workshop_name='园区剪切', process_name='包装', output_weight_tons=175.421, source_id='bz-1'),
            MesWorkshopProcessRecord(business_date=REPORT_DATE, workshop_name='园区剪切', process_name='入库', output_weight_tons=103.809, source_id='rk-1'),
            MesWorkshopProcessRecord(business_date=REPORT_DATE, workshop_name='园区剪切', process_name='退火板', output_weight_tons=63.183, source_id='thb-1'),
        ])
        db.commit()

        payload = build_workshop_daily_cards(db, target_date=REPORT_DATE)
        park = next(card for card in payload['cards'] if card['workshop_name'] == '园区剪切')

        assert park['fields']['飞剪下机']['value'] == 74.17
        assert park['fields']['重卷下机']['value'] == 12.685
        assert park['fields']['包装']['value'] == 175.421
        assert park['fields']['合计']['value'] == 166.992
        assert park['fields']['今日吨耗']['denominator_field'] == '包装'
    finally:
        db.close()


def test_render_workshop_cards_displays_missing_as_slash() -> None:
    text = render_workshop_cards({
        'cards': [
            {
                'workshop_name': '园区剪切',
                'date_label': '6月16日',
                'fields': {
                    '飞剪下机': {'value': 74.17, 'unit': ''},
                    '外加工': {'value': None, 'unit': ''},
                },
                'gaps': ['外加工'],
            }
        ]
    })

    assert '园区剪切' in text
    assert '飞剪下机74.17' in text
    assert '外加工/' in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest -q tests/test_workshop_daily_cards.py
```

Expected: FAIL because `workshop_daily_cards` does not exist.

- [ ] **Step 3: Implement workshop card service**

Create `backend/app/services/report/workshop_daily_cards.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.mes import MesWorkshopProcessRecord


WORKSHOP_CARD_NAMES = [
    '铸锭', '铸二', '铸三', '热轧', '淬火', '冷轧1650', '冷轧1850', '冷轧2050',
    '新厂在线', '园区在线', '拉矫', '精整', '园区剪切', '回收', '大修',
]


def _month_day(target_date: date) -> str:
    return f'{target_date.month}月{target_date.day}日'


def _sum_process(rows: list[MesWorkshopProcessRecord], *tokens: str) -> float | None:
    total = 0.0
    count = 0
    for row in rows:
        text = f'{row.workshop_name or ""} {row.process_name or ""} {row.device_name or ""}'
        if all(token in text for token in tokens):
            total += float(row.output_weight_tons or 0)
            count += 1
    return round(total, 3) if count else None


def _field(value: Any, unit: str = '', *, source: str = 'mes_workshop_process_records', denominator_field: str | None = None) -> dict[str, Any]:
    payload = {'value': value, 'unit': unit, 'source': source}
    if denominator_field:
        payload['denominator_field'] = denominator_field
    return payload


def _park_shearing_card(rows: list[MesWorkshopProcessRecord], target_date: date) -> dict[str, Any]:
    fly = _sum_process(rows, '园区剪切', '飞剪')
    rewind = _sum_process(rows, '园区剪切', '重卷')
    packaging = _sum_process(rows, '园区剪切', '包装')
    inbound = _sum_process(rows, '园区剪切', '入库')
    anneal_plate = _sum_process(rows, '园区剪切', '退火板')
    total = None
    if inbound is not None or anneal_plate is not None:
        total = round(float(inbound or 0) + float(anneal_plate or 0), 3)
    fields = {
        '飞剪下机': _field(fly),
        '重卷下机': _field(rewind),
        '包装': _field(packaging),
        '外加工': _field(None, source='manual_or_mes_missing'),
        '入库产量': _field(inbound),
        '退火板': _field(anneal_plate),
        '合计': _field(total, source='computed'),
        '今日吨耗': _field(None, source='energy_summary', denominator_field='包装'),
        '月吨耗': _field(None, source='energy_summary_month', denominator_field='包装'),
    }
    return {
        'workshop_name': '园区剪切',
        'date_label': _month_day(target_date),
        'fields': fields,
        'gaps': [name for name, field in fields.items() if field.get('value') is None],
    }


def _empty_card(workshop_name: str, target_date: date) -> dict[str, Any]:
    return {
        'workshop_name': workshop_name,
        'date_label': _month_day(target_date),
        'fields': {'产量': _field(None)},
        'gaps': ['产量'],
    }


def build_workshop_daily_cards(db: Session, *, target_date: date) -> dict[str, Any]:
    rows = (
        db.query(MesWorkshopProcessRecord)
        .filter(MesWorkshopProcessRecord.business_date == target_date)
        .all()
    )
    cards = []
    for name in WORKSHOP_CARD_NAMES:
        if name == '园区剪切':
            cards.append(_park_shearing_card(rows, target_date))
        else:
            cards.append(_empty_card(name, target_date))
    return {'target_date': target_date.isoformat(), 'cards': cards}


def _display_value(value: Any) -> str:
    if value in (None, ''):
        return '/'
    number = float(value)
    text = f'{number:.3f}'.rstrip('0').rstrip('.')
    return text or '0'


def render_workshop_cards(cards_payload: dict[str, Any]) -> str:
    parts = ['【车间分项】']
    for card in cards_payload.get('cards') or []:
        parts.append(str(card.get('workshop_name') or '未命名车间'))
        parts.append(str(card.get('date_label') or ''))
        for label, field in (card.get('fields') or {}).items():
            parts.append(f"{label}{_display_value(field.get('value'))}{field.get('unit') or ''}")
        parts.append('')
    return '\n'.join(parts).strip()
```

- [ ] **Step 4: Append workshop cards into template daily report payload**

Modify `backend/app/services/report/template_daily_report.py` near `build_template_daily_report_payload`:

```python
from app.services.report.workshop_daily_cards import build_workshop_daily_cards, render_workshop_cards
```

Inside `build_template_daily_report_payload` after `validation = ...`:

```python
    workshop_cards = build_workshop_daily_cards(db, target_date=target_date)
    card_text = render_workshop_cards(workshop_cards)
    text = str(validation.get("text") or "")
    validation["text"] = f"{text}\n\n{card_text}".strip()
```

And include in return payload:

```python
        "workshop_cards": workshop_cards,
```

- [ ] **Step 5: Run card and existing template tests**

```bash
cd backend
pytest -q tests/test_workshop_daily_cards.py tests/test_template_daily_report.py tests/test_report_generation.py
```

Expected: PASS. If existing locked template tests fail because card text is appended, update only the payload integration test and keep `render_template_daily_report()` pure so locked template text still passes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/workshop_daily_cards.py backend/app/services/report/template_daily_report.py backend/tests/test_workshop_daily_cards.py
git commit -m "feat: add workshop daily report cards"
```

---

### Task 5: Report Versioning and 9:35 Diff Logic

**Files:**
- Create: `backend/app/services/report/daily_report_versions.py`
- Test: `backend/tests/test_daily_report_versions.py`
- Modify: `backend/app/tasks/daily_report.py`

**Interfaces:**
- Produces: `mark_initial_version(report: DailyReport, payload: dict) -> None`, `build_correction_diff(report: DailyReport, new_payload: dict) -> dict`, `apply_correction_version(report: DailyReport, new_payload: dict, diff: dict) -> bool`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_daily_report_versions.py`:

```python
from __future__ import annotations

from datetime import date

from app.models.reports import DailyReport
from app.services.report.daily_report_versions import apply_correction_version, build_correction_diff, mark_initial_version


def _report() -> DailyReport:
    return DailyReport(report_date=date(2026, 6, 16), report_type='production', report_data={})


def test_mark_initial_version_stores_snapshot() -> None:
    report = _report()
    payload = {'text': '初版', 'facts': {'values': {'total_output_daily': 100}}, 'workshop_cards': {'cards': []}}

    mark_initial_version(report, payload)

    versions = report.report_data['daily_report_versions']
    assert versions['initial']['text'] == '初版'
    assert versions['initial']['key_values']['total_output_daily'] == 100
    assert versions['initial']['version_label'] == '7:30初版'


def test_correction_diff_detects_key_field_change() -> None:
    report = _report()
    mark_initial_version(report, {'text': '初版', 'facts': {'values': {'total_output_daily': 100}}, 'workshop_cards': {'cards': []}})

    diff = build_correction_diff(report, {'text': '修正版', 'facts': {'values': {'total_output_daily': 120}}, 'workshop_cards': {'cards': []}})

    assert diff['changed'] is True
    assert diff['items'][0] == {'field': 'total_output_daily', 'before': 100, 'after': 120}


def test_apply_correction_skips_when_no_key_change() -> None:
    report = _report()
    mark_initial_version(report, {'text': '初版', 'facts': {'values': {'total_output_daily': 100}}, 'workshop_cards': {'cards': []}})
    diff = build_correction_diff(report, {'text': '修正版', 'facts': {'values': {'total_output_daily': 100}}, 'workshop_cards': {'cards': []}})

    applied = apply_correction_version(report, {'text': '修正版', 'facts': {'values': {'total_output_daily': 100}}, 'workshop_cards': {'cards': []}}, diff)

    assert applied is False
    assert 'correction' not in report.report_data['daily_report_versions']
```

- [ ] **Step 2: Run failing test**

```bash
cd backend
pytest -q tests/test_daily_report_versions.py
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement versioning service**

Create `backend/app/services/report/daily_report_versions.py`:

```python
from __future__ import annotations

from typing import Any

from app.models.reports import DailyReport


KEY_FIELDS = (
    'total_output_daily',
    'finished_inbound_daily',
    'daily_yield_rate',
    'total_electricity_kwh',
    'total_gas_m3',
    'cost_per_ton',
)


def _key_values(payload: dict[str, Any]) -> dict[str, Any]:
    values = ((payload.get('facts') or {}).get('values') or {})
    return {field: values.get(field) for field in KEY_FIELDS if field in values}


def _versions(report: DailyReport) -> dict[str, Any]:
    data = dict(report.report_data or {})
    versions = dict(data.get('daily_report_versions') or {})
    data['daily_report_versions'] = versions
    report.report_data = data
    return versions


def mark_initial_version(report: DailyReport, payload: dict[str, Any]) -> None:
    versions = _versions(report)
    versions['initial'] = {
        'version_label': '7:30初版',
        'text': payload.get('text') or '',
        'key_values': _key_values(payload),
        'workshop_cards': payload.get('workshop_cards') or {},
    }
    report.final_text_summary = str(payload.get('text') or '')


def build_correction_diff(report: DailyReport, new_payload: dict[str, Any]) -> dict[str, Any]:
    versions = _versions(report)
    before = dict((versions.get('initial') or {}).get('key_values') or {})
    after = _key_values(new_payload)
    items = [
        {'field': field, 'before': before.get(field), 'after': after.get(field)}
        for field in sorted(set(before) | set(after))
        if before.get(field) != after.get(field)
    ]
    return {'changed': bool(items), 'items': items}


def apply_correction_version(report: DailyReport, new_payload: dict[str, Any], diff: dict[str, Any]) -> bool:
    if not diff.get('changed'):
        return False
    versions = _versions(report)
    versions['correction'] = {
        'version_label': '补录修正版',
        'text': new_payload.get('text') or '',
        'key_values': _key_values(new_payload),
        'workshop_cards': new_payload.get('workshop_cards') or {},
        'diff': diff,
    }
    report.final_text_summary = str(new_payload.get('text') or '')
    return True
```

- [ ] **Step 4: Split daily report task functions**

Modify `backend/app/tasks/daily_report.py`:

```python
from app.models.reports import DailyReport
from app.services.report import daily_report_versions
```

Add:

```python
def generate_initial_daily_report(target_date: date | None = None) -> dict[str, str]:
    business_date = target_date or last_completed_production_business_date()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        aggregator_agent.execute(db=session, target_date=business_date)
        session.commit()
        payload = template_daily_report.apply_template_daily_report_to_latest_report(session, business_date)
        report = session.query(DailyReport).filter_by(report_date=business_date, report_type='production').first()
        if report is not None:
            daily_report_versions.mark_initial_version(report, payload)
        reporter_agent.execute(db=session, target_date=business_date)
        session.commit()
    return {'status': 'ok', 'business_date': business_date.isoformat(), 'version': 'initial'}


def generate_correction_daily_report(target_date: date | None = None) -> dict[str, str]:
    business_date = target_date or last_completed_production_business_date()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        payload = template_daily_report.apply_template_daily_report_to_latest_report(session, business_date)
        report = session.query(DailyReport).filter_by(report_date=business_date, report_type='production').first()
        if report is None:
            session.commit()
            return {'status': 'skipped', 'business_date': business_date.isoformat(), 'version': 'correction'}
        diff = daily_report_versions.build_correction_diff(report, payload)
        changed = daily_report_versions.apply_correction_version(report, payload, diff)
        if changed:
            reporter_agent.execute(db=session, target_date=business_date)
        session.commit()
    return {'status': 'sent' if changed else 'unchanged', 'business_date': business_date.isoformat(), 'version': 'correction'}
```

Keep `generate_daily_reports()` as a backward-compatible wrapper that calls `generate_initial_daily_report()`.

- [ ] **Step 5: Run tests**

```bash
cd backend
pytest -q tests/test_daily_report_versions.py tests/test_daily_report_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/daily_report_versions.py backend/app/tasks/daily_report.py backend/tests/test_daily_report_versions.py backend/tests/test_daily_report_task.py
git commit -m "feat: version initial and correction daily reports"
```

---

### Task 6: Scheduler Jobs for 7:30 and 9:35

**Files:**
- Modify: `backend/app/core/scheduler.py`
- Test: `backend/tests/test_scheduler.py`
- Modify carefully: `backend/app/main.py`

**Interfaces:**
- Consumes: `generate_initial_daily_report`, `generate_correction_daily_report`.
- Produces scheduler jobs `daily_report_initial_0730`, `daily_report_correction_0935`.

- [ ] **Step 1: Write failing scheduler test**

Modify `backend/tests/test_scheduler.py`:

```python
def test_setup_scheduler_registers_daily_report_initial_and_correction_jobs(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_module.settings, 'MES_ADAPTER', 'null')
    monkeypatch.setattr(scheduler_module.settings, 'IOT_ENERGY_ADAPTER', 'null')
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)

    assert scheduler.jobs['daily_report_initial_0730']['trigger'] == 'cron'
    assert scheduler.jobs['daily_report_initial_0730']['kwargs']['hour'] == 7
    assert scheduler.jobs['daily_report_initial_0730']['kwargs']['minute'] == 30
    assert scheduler.jobs['daily_report_correction_0935']['trigger'] == 'cron'
    assert scheduler.jobs['daily_report_correction_0935']['kwargs']['hour'] == 9
    assert scheduler.jobs['daily_report_correction_0935']['kwargs']['minute'] == 35
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest -q tests/test_scheduler.py::test_setup_scheduler_registers_daily_report_initial_and_correction_jobs
```

Expected: FAIL because jobs are not registered.

- [ ] **Step 3: Modify scheduler**

In `backend/app/core/scheduler.py`, change the daily report import and jobs:

```python
from app.tasks.daily_report import generate_correction_daily_report, generate_initial_daily_report
```

Replace the old `daily_report` cron job with:

```python
    _add_job_once(active_scheduler, generate_initial_daily_report, 'cron', job_id='daily_report_initial_0730', hour=7, minute=30)
    _add_job_once(active_scheduler, generate_correction_daily_report, 'cron', job_id='daily_report_correction_0935', hour=9, minute=35)
```

Keep the old job id only if tests or ops require compatibility:

```python
    _add_job_once(active_scheduler, generate_initial_daily_report, 'cron', job_id='daily_report', hour=7, minute=30)
```

If compatibility job is kept, document that it points to initial generation.

- [ ] **Step 4: Remove duplicate hourly report send from `main.py` if it conflicts**

Inspect `_run_orchestration_pipeline` in `backend/app/main.py`. It currently calls aggregator/reporter hourly. Do not delete it in this task unless tests prove duplicate report sends. If duplicate sends happen, change it to aggregate only and not call `reporter_agent.execute`.

Add a regression test before removing reporter behavior.

- [ ] **Step 5: Run scheduler tests**

```bash
cd backend
pytest -q tests/test_scheduler.py tests/test_daily_report_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/scheduler.py backend/tests/test_scheduler.py backend/app/main.py backend/tests/test_daily_report_task.py
git commit -m "feat: schedule daily report correction workflow"
```

---

### Task 7: Queue Daily Report Secretary Robot Messages Through Outbox

**Files:**
- Create: `backend/app/services/report/daily_report_agent_delivery.py`
- Test: `backend/tests/test_daily_report_agent_delivery.py`
- Modify: `backend/app/tasks/daily_report.py`

**Interfaces:**
- Produces: `queue_daily_report_secretary_message(db, report, version_label: str, content: str, diff: dict | None = None) -> AgentOutboxMessage`.

- [ ] **Step 1: Write failing outbox test**

Create `backend/tests/test_daily_report_agent_delivery.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentOutboxMessage
from app.models.reports import DailyReport
from app.services.agent_personal_bootstrap_service import ensure_zhang_zhaojia_personal_agents
from app.services.agent_robot_bootstrap_service import ensure_zzj_custom_robot_channels
from app.services.report.daily_report_agent_delivery import queue_daily_report_secretary_message


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_queue_daily_report_secretary_message_uses_custom_robot_channel() -> None:
    db = _session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        ensure_zzj_custom_robot_channels(db, apply=True, dry_run=False)
        report = DailyReport(report_date=date(2026, 6, 16), report_type='production', final_text_summary='日报正文')
        db.add(report)
        db.flush()

        message = queue_daily_report_secretary_message(db, report=report, version_label='7:30初版', content='日报正文')

        assert message.status == 'pending'
        assert message.title == '6月16日生产日报（7:30初版）'
        assert message.business_date == date(2026, 6, 16)
        assert db.query(AgentOutboxMessage).count() == 1
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest -q tests/test_daily_report_agent_delivery.py
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement delivery service**

Create `backend/app/services/report/daily_report_agent_delivery.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentOutboxMessage
from app.models.reports import DailyReport
from app.services import agent_communication_service


DAILY_REPORT_AGENT_CODE = 'daily_report_secretary_zzj'
DAILY_REPORT_CHANNEL_KEY = 'DINGTALK_ROBOT_DAILY_REPORT_WEBHOOK'
DAILY_REPORT_CHANNEL_TYPE = 'dingtalk_custom_robot'


def _month_day(report: DailyReport) -> str:
    return f'{report.report_date.month}月{report.report_date.day}日'


def queue_daily_report_secretary_message(
    db: Session,
    *,
    report: DailyReport,
    version_label: str,
    content: str,
    diff: dict[str, Any] | None = None,
) -> AgentOutboxMessage:
    title = f'{_month_day(report)}生产日报（{version_label}）'
    payload = {
        'report_id': report.id,
        'report_date': report.report_date.isoformat(),
        'version_label': version_label,
        'diff': diff or {},
    }
    return agent_communication_service.queue_bound_message(
        db,
        agent_code=DAILY_REPORT_AGENT_CODE,
        channel_key=DAILY_REPORT_CHANNEL_KEY,
        channel_type=DAILY_REPORT_CHANNEL_TYPE,
        title=title,
        content=content,
        business_date=report.report_date,
        source_summary='daily_report_secretary',
        payload=payload,
        dedupe_key=f'daily-report:{report.report_date.isoformat()}:{version_label}',
        dedupe_window_minutes=60 * 24,
    )
```

- [ ] **Step 4: Wire delivery into daily task**

In `backend/app/tasks/daily_report.py`, after marking initial version:

```python
from app.services.report.daily_report_agent_delivery import queue_daily_report_secretary_message
```

For initial:

```python
if report is not None and report.final_text_summary:
    queue_daily_report_secretary_message(
        session,
        report=report,
        version_label='7:30初版',
        content=report.final_text_summary,
    )
```

For correction, only when changed:

```python
if changed and report.final_text_summary:
    queue_daily_report_secretary_message(
        session,
        report=report,
        version_label='补录修正版',
        content=report.final_text_summary,
        diff=diff,
    )
```

Do not call DingTalk directly. Let the scheduled outbox dispatcher send.

- [ ] **Step 5: Run delivery tests**

```bash
cd backend
pytest -q tests/test_daily_report_agent_delivery.py tests/test_daily_report_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/daily_report_agent_delivery.py backend/app/tasks/daily_report.py backend/tests/test_daily_report_agent_delivery.py backend/tests/test_daily_report_task.py
git commit -m "feat: queue daily report secretary messages"
```

---

### Task 8: Management UI Visibility

**Files:**
- Modify: `backend/app/services/agent_management_overview_service.py`
- Modify: `frontend/src/views/manage/admin/AgentManagementPage.vue`
- Modify: `frontend/src/views/manage/channels/CommunicationChannelsPage.vue`
- Test: existing frontend tests if available; otherwise add lightweight text/route checks under `backend/tests/test_frontend_refactor_blueprint.py`.

**Interfaces:**
- Backend overview includes `report_workflow` summary.
- Frontend displays `7:30初版`, `9:35修正版`, `RAG文档`, `真实发送`.

- [ ] **Step 1: Write failing backend/frontend expectation test**

Add to `backend/tests/test_frontend_refactor_blueprint.py`:

```python
from pathlib import Path


def test_agent_management_page_mentions_daily_report_workflow() -> None:
    source = Path('frontend/src/views/manage/admin/AgentManagementPage.vue').read_text(encoding='utf-8')
    assert '7:30初版' in source
    assert '9:35修正版' in source


def test_channels_page_labels_dingtalk_custom_robot() -> None:
    source = Path('frontend/src/views/manage/channels/CommunicationChannelsPage.vue').read_text(encoding='utf-8')
    assert 'dingtalk_custom_robot' in source
    assert '钉钉机器人' in source
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest -q backend/tests/test_frontend_refactor_blueprint.py::test_agent_management_page_mentions_daily_report_workflow backend/tests/test_frontend_refactor_blueprint.py::test_channels_page_labels_dingtalk_custom_robot
```

Expected: FAIL because page text is not present.

- [ ] **Step 3: Update channels page label**

Modify `frontend/src/views/manage/channels/CommunicationChannelsPage.vue`:

```js
const labels = {
  dingtalk_group: '钉钉群',
  dingtalk_work_notice: '钉钉工作通知',
  dingtalk_work_notification: '钉钉工作通知',
  dingtalk_custom_robot: '钉钉机器人',
  wecom_group: '企业微信群',
  internal_notice: '内部通知'
}
```

- [ ] **Step 4: Update Agent page workflow section**

Add a small panel in `frontend/src/views/manage/admin/AgentManagementPage.vue` metrics/grid:

```vue
<section class="xt-agent-management__panel">
  <header>
    <h2>日报流程</h2>
    <span>自动发送</span>
  </header>
  <div class="xt-agent-management__list">
    <article class="xt-agent-management__row">
      <div>
        <b>7:30初版</b>
        <small>全厂日报 + 所有车间分项卡</small>
      </div>
      <span class="xt-agent-management__tag">启用</span>
    </article>
    <article class="xt-agent-management__row">
      <div>
        <b>9:35修正版</b>
        <small>仅关键字段变化时发送</small>
      </div>
      <span class="xt-agent-management__tag">启用</span>
    </article>
  </div>
</section>
```

- [ ] **Step 5: Run UI tests/build**

```bash
pytest -q backend/tests/test_frontend_refactor_blueprint.py
cd frontend
npm test -- --run
npm run build
```

Expected: PASS. If `npm test -- --run` is not supported, record the exact command failure and run the repository’s available frontend test command.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/manage/admin/AgentManagementPage.vue frontend/src/views/manage/channels/CommunicationChannelsPage.vue backend/tests/test_frontend_refactor_blueprint.py
git commit -m "feat: surface daily report agent workflow"
```

---

### Task 9: End-to-End Validation and Cloud Rollout

**Files:**
- No new source files unless a test exposes a bug.
- Update docs only if validation reveals an operational runbook gap.

**Interfaces:**
- Uses scripts and APIs created in previous tasks.

- [ ] **Step 1: Run backend focused tests**

```bash
cd backend
pytest -q \
  tests/test_agent_sop_bootstrap_service.py \
  tests/test_rag_bootstrap_service.py \
  tests/test_mes_data_dictionary_service.py \
  tests/test_workshop_daily_cards.py \
  tests/test_daily_report_versions.py \
  tests/test_daily_report_agent_delivery.py \
  tests/test_daily_report_task.py \
  tests/test_scheduler.py
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run full backend tests if runtime allows**

```bash
cd backend
pytest -q
```

Expected: PASS or documented known environment-only failure. Do not claim full pass if it fails.

- [ ] **Step 4: Apply cloud bootstrap safely**

Preview first:

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=/srv/aluminum-bypass/backend ./.venv/bin/python scripts/bootstrap_agent_sop.py
PYTHONPATH=/srv/aluminum-bypass/backend ./.venv/bin/python scripts/bootstrap_rag_knowledge.py --reference-root /srv/aluminum-bypass/reference/output-skill
```

Apply only after previews look correct:

```bash
PYTHONPATH=/srv/aluminum-bypass/backend ./.venv/bin/python scripts/bootstrap_agent_sop.py --apply
PYTHONPATH=/srv/aluminum-bypass/backend ./.venv/bin/python scripts/bootstrap_rag_knowledge.py --reference-root /srv/aluminum-bypass/reference/output-skill --apply
```

Expected: SOP applied to 6 agents; RAG imports stable documents; no secret printed.

- [ ] **Step 5: Cloud smoke**

Run:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/healthz
curl -fsS http://127.0.0.1:8000/api/v1/readyz
```

Expected: both return OK/ready.

- [ ] **Step 6: Browser QA**

Open:

- `https://xtmijd.com/manage/admin/agents`
- `https://xtmijd.com/manage/channels`
- `https://xtmijd.com/manage/rag`
- `https://xtmijd.com/manage/daily-report`

Verify:

- Agent page shows 7:30 and 9:35 workflow.
- Channel page shows DingTalk robots as real send.
- RAG page shows imported output-skill documents.
- Daily report preview includes workshop cards.
- No console red errors.
- No network 500.

- [ ] **Step 7: Manual dry smoke for report generation**

On cloud, run for a safe historical date:

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=/srv/aluminum-bypass/backend ./.venv/bin/python - <<'PY'
from datetime import date
from app.tasks.daily_report import generate_initial_daily_report, generate_correction_daily_report
print(generate_initial_daily_report(date(2026, 6, 16)))
print(generate_correction_daily_report(date(2026, 6, 16)))
PY
```

Expected:

- Initial queues one outbox message.
- Correction queues only if key fields changed.
- No direct DingTalk call outside outbox.

- [ ] **Step 8: Final commit if validation fixes were needed**

```bash
git status --short
git add <changed-files>
git commit -m "fix: stabilize daily report agent workflow"
```

Skip if no files changed.

---

## Self-Review

Spec coverage:

- Six Agent SOP: Task 1.
- RAG knowledge bootstrap: Task 2.
- MES/system dictionary: Task 3.
- All workshop cards and park shearing card: Task 4.
- 7:30 initial and 9:35 correction versions: Task 5 and Task 6.
- Outbox-only DingTalk delivery: Task 7.
- Management UI visibility: Task 8.
- Cloud validation and browser QA: Task 9.

Placeholder scan:

- 占位词扫描通过；计划没有未完成占位项。
- Each task has concrete file paths, test commands, and expected result.

Type consistency:

- `build_workshop_daily_cards(db, target_date=...)` is defined in Task 4 and consumed by `template_daily_report`.
- `mark_initial_version`, `build_correction_diff`, `apply_correction_version` are defined in Task 5 and consumed by daily tasks.
- `queue_daily_report_secretary_message` is defined in Task 7 and consumed by daily tasks.

Risk notes:

- Existing hourly orchestration in `backend/app/main.py` may duplicate reporter sends. Task 6 explicitly requires checking and testing before changing it.
- Current plan avoids migrations by using `DailyReport.report_data`. If later query performance or audit needs demand a table, create a separate migration plan.
- Cloud RAG import needs output-skill files mounted to `/srv/aluminum-bypass/reference/output-skill` or another explicit path.

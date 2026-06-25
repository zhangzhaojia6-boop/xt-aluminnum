from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.core.redaction import redact_secret_text
from app.models.hermes_factory_brain import HermesCodexConstructionRun
from app.models.system import User


@dataclass(frozen=True, slots=True)
class CodexConstructionRequestResult:
    status: str
    run_id: int | None
    message: str


def request_codex_construction(
    db: Session,
    *,
    actor: User,
    request_text: str,
    trace_id: str,
    construction_type: str,
) -> CodexConstructionRequestResult:
    if not bool(getattr(settings, 'HERMES_CODEX_CONSTRUCTION_ENABLED', False)):
        return CodexConstructionRequestResult(
            status='disabled',
            run_id=None,
            message='Codex 施工能力当前未开启。',
        )
    if not _is_root_owner(actor):
        return CodexConstructionRequestResult(
            status='denied',
            run_id=None,
            message='只有 root_owner 可以触发 Codex 施工。',
        )
    run = HermesCodexConstructionRun(
        trace_id=trace_id,
        request_text=redact_secret_text(request_text),
        construction_type=construction_type,
        authorization_level='root_owner',
        status='requested',
        payload={
            'steps_required': ['plan', 'execute', 'test', 'deploy_or_report', 'rollback_note'],
            'construction_type': construction_type,
        },
        requested_by_id=actor.id,
    )
    db.add(run)
    db.flush()
    return CodexConstructionRequestResult(
        status='requested',
        run_id=run.id,
        message='Codex 施工请求已记录，等待执行器接管。',
    )


def _is_root_owner(actor: User) -> bool:
    owner_ids = set(getattr(settings, 'hermes_owner_dingtalk_user_ids', set()) or set())
    identity_values = {
        str(getattr(actor, 'dingtalk_user_id', '') or '').strip(),
        str(getattr(actor, 'dingtalk_union_id', '') or '').strip(),
    }
    identity_values.discard('')
    return bool(owner_ids & identity_values)

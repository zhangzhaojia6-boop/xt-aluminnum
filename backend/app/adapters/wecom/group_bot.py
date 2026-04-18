from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Mapping

import httpx

from app.adapters.workflow.base import WorkflowDispatchEnvelope, WorkflowPublishResult
from app.config import Settings, settings as runtime_settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeComBotTarget:
    target_type: str
    target_key: str
    webhook_url: str | None


@dataclass(frozen=True, slots=True)
class WeComBotMessage:
    message_kind: str
    title: str
    content: str


class WeComGroupBotPublisher:
    name = 'wecom_group_bot'

    def __init__(self, *, settings: Settings | None = None, sender=None):
        self._settings = settings or runtime_settings
        self._sender = sender or self._default_sender

    def supports(self, workflow_event: Mapping[str, Any]) -> bool:
        if not self._settings.WECOM_BOT_ENABLED:
            return False
        if self._resolve_message_kind(workflow_event) is None:
            return False
        return self._resolve_target(workflow_event) is not None

    def build_dispatch_envelope(self, realtime_event: Mapping[str, Any]) -> WorkflowDispatchEnvelope:
        payload = realtime_event.get('payload') or {}
        workflow_event = payload.get('workflow_event') or {}
        return WorkflowDispatchEnvelope(
            dispatch_key=f"test:{realtime_event.get('id') or 'no-id'}",
            realtime_event_id=self._normalize_optional_int(realtime_event.get('id')),
            realtime_event_type=str(realtime_event.get('event_type') or workflow_event.get('event_type') or ''),
            realtime_event=dict(realtime_event),
            workflow_event=dict(workflow_event),
            attempt=1,
        )

    def publish(self, envelope: WorkflowDispatchEnvelope) -> WorkflowPublishResult:
        workflow_event = dict(envelope.workflow_event)
        message_kind = self._resolve_message_kind(workflow_event)
        if message_kind is None:
            return WorkflowPublishResult(
                publisher=self.name,
                status='skipped',
                detail='unsupported workflow event for wecom group bot',
            )

        target = self._resolve_target(workflow_event)
        if target is None:
            return WorkflowPublishResult(
                publisher=self.name,
                status='skipped',
                detail='no delivery target resolved for wecom group bot',
            )

        message = self._build_message(envelope, target=target, message_kind=message_kind)
        metadata = {
            'target_type': target.target_type,
            'target_key': target.target_key,
            'message_kind': message.message_kind,
            'title': message.title,
        }

        if self._settings.WECOM_BOT_DRY_RUN:
            logger.info('WeCom group bot dry-run %s -> %s:%s', message.message_kind, target.target_type, target.target_key)
            return WorkflowPublishResult(
                publisher=self.name,
                status='dry_run',
                detail='dry-run only, message not sent',
                metadata=metadata,
            )

        if not target.webhook_url:
            raise RuntimeError(f'WeCom group bot target {target.target_type}:{target.target_key} has no webhook URL configured')

        request_body = {
            'msgtype': 'text',
            'text': {
                'content': f'{message.title}\n{message.content}',
            },
        }
        try:
            response = self._sender(
                url=target.webhook_url,
                json=request_body,
                timeout=self._settings.WECOM_BOT_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            logger.warning('WeCom group bot timeout for %s:%s', target.target_type, target.target_key, exc_info=True)
            raise RuntimeError(f'WeCom group bot timed out: {exc}') from exc
        except httpx.HTTPError as exc:
            logger.warning('WeCom group bot request failed for %s:%s', target.target_type, target.target_key, exc_info=True)
            raise RuntimeError(f'WeCom group bot request failed: {exc}') from exc

        status_code = int(getattr(response, 'status_code', 0) or 0)
        if status_code < 200 or status_code >= 300:
            logger.warning(
                'WeCom group bot non-2xx response %s for %s:%s',
                status_code,
                target.target_type,
                target.target_key,
            )
            raise RuntimeError(f'WeCom group bot non-2xx response: {status_code}')

        response_payload = self._load_response_json(response)
        errcode = response_payload.get('errcode')
        if errcode not in {None, 0, '0'}:
            errmsg = str(response_payload.get('errmsg') or response_payload)
            logger.warning(
                'WeCom group bot business error for %s:%s: %s',
                target.target_type,
                target.target_key,
                errmsg,
            )
            raise RuntimeError(f'WeCom group bot business error: {errmsg}')

        logger.info('WeCom group bot delivered %s -> %s:%s', message.message_kind, target.target_type, target.target_key)
        metadata['status_code'] = status_code
        return WorkflowPublishResult(
            publisher=self.name,
            status='sent',
            detail='wecom group bot sent',
            metadata=metadata,
        )

    def _resolve_message_kind(self, workflow_event: Mapping[str, Any]) -> str | None:
        event_type = str(workflow_event.get('event_type') or '')
        payload = workflow_event.get('payload') if isinstance(workflow_event.get('payload'), Mapping) else {}
        if event_type == 'report_published':
            return 'daily_report_published'
        if event_type in {'attendance_confirmed', 'report_reviewed'}:
            return 'review_completed'
        if payload and payload.get('reminder_reason'):
            return 'reminder'
        return None

    def _resolve_target(self, workflow_event: Mapping[str, Any]) -> WeComBotTarget | None:
        payload = workflow_event.get('payload') if isinstance(workflow_event.get('payload'), Mapping) else {}
        requested_target = str(payload.get('delivery_target') or '').strip().lower() if payload else ''
        requested_target_key = str(payload.get('delivery_target_key') or '').strip() if payload else ''
        requested_scope = str(payload.get('delivery_scope') or '').strip().lower() if payload else ''
        team_id = self._normalize_optional_int(workflow_event.get('team_id'))
        workshop_id = self._normalize_optional_int(workflow_event.get('workshop_id'))
        event_type = str(workflow_event.get('event_type') or '')
        scope_type = str(workflow_event.get('scope_type') or '')

        if requested_target == 'management':
            return self._build_management_target()
        if requested_scope == 'factory':
            return self._build_management_target()
        if requested_target == 'workshop' and requested_target_key.isdigit():
            return self._build_workshop_target(int(requested_target_key))
        if requested_target == 'team' and team_id is not None:
            return self._build_team_target(team_id)
        if requested_target == 'workshop' and workshop_id is not None:
            return self._build_workshop_target(workshop_id)
        if requested_scope.startswith('workshop:') and workshop_id is not None:
            return self._build_workshop_target(workshop_id)

        if event_type.startswith('report_') or scope_type == 'factory':
            return self._build_management_target()
        if team_id is not None:
            return self._build_team_target(team_id)
        if workshop_id is not None:
            return self._build_workshop_target(workshop_id)
        return self._build_management_target()

    def _build_management_target(self) -> WeComBotTarget:
        return WeComBotTarget(
            target_type='management',
            target_key='management',
            webhook_url=self._preferred_webhook(self._settings.WECOM_BOT_MANAGEMENT_WEBHOOK_URL),
        )

    def _build_workshop_target(self, workshop_id: int) -> WeComBotTarget:
        configured = self._settings.wecom_bot_workshop_webhook_map.get(str(workshop_id))
        return WeComBotTarget(
            target_type='workshop',
            target_key=str(workshop_id),
            webhook_url=self._preferred_webhook(configured),
        )

    def _build_team_target(self, team_id: int) -> WeComBotTarget:
        configured = self._settings.wecom_bot_team_webhook_map.get(str(team_id))
        return WeComBotTarget(
            target_type='team',
            target_key=str(team_id),
            webhook_url=self._preferred_webhook(configured),
        )

    def _preferred_webhook(self, configured: str | None) -> str | None:
        if configured:
            return configured
        if self._settings.WECOM_BOT_WEBHOOK_URL:
            return self._settings.WECOM_BOT_WEBHOOK_URL
        return None

    def _build_message(
        self,
        envelope: WorkflowDispatchEnvelope,
        *,
        target: WeComBotTarget,
        message_kind: str,
    ) -> WeComBotMessage:
        workflow_event = dict(envelope.workflow_event)
        realtime_payload = (
            envelope.realtime_event.get('payload')
            if isinstance(envelope.realtime_event.get('payload'), Mapping)
            else {}
        )
        context = self._build_context(workflow_event, realtime_payload, target=target)

        if message_kind == 'daily_report_published':
            title = f"【日报发布】{context['report_date'] or context['event_date']}"
            content = '\n'.join(
                [
                    f"类型：{context['report_type_label']}",
                    f"范围：{context['scope_label']}",
                    f"状态：{context['status_label']}",
                    f"班次数：{context['published_shift_count']}",
                    f"时间：{context['occurred_at_label']}",
                ]
            )
            return WeComBotMessage(message_kind=message_kind, title=title, content=content)

        if message_kind == 'review_completed':
            title = f"【审核完成】{context['scope_label']}"
            content = '\n'.join(
                [
                    f"事项：{context['event_label']}",
                    f"状态：{context['status_label']}",
                    f"对象：{context['entity_label']}",
                    f"时间：{context['occurred_at_label']}",
                    f"异常数：{context['exception_count']}",
                ]
            )
            return WeComBotMessage(message_kind=message_kind, title=title, content=content)

        reminder_reason = context['reminder_reason'] or '请尽快处理当前流程事项'
        title = f"【流程催报】{context['scope_label']}"
        content = '\n'.join(
            [
                f"事项：{reminder_reason}",
                f"对象：{context['entity_label']}",
                f"卡号：{context['tracking_card_no'] or '-'}",
                f"时间：{context['occurred_at_label']}",
            ]
        )
        return WeComBotMessage(message_kind=message_kind, title=title, content=content)

    def _build_context(
        self,
        workflow_event: Mapping[str, Any],
        realtime_payload: Mapping[str, Any],
        *,
        target: WeComBotTarget,
    ) -> dict[str, str]:
        payload = workflow_event.get('payload') if isinstance(workflow_event.get('payload'), Mapping) else {}
        occurred_at = self._format_datetime(workflow_event.get('occurred_at'))
        report_type = str(payload.get('report_type') or '')
        return {
            'event_label': self._event_label(str(workflow_event.get('event_type') or '')),
            'event_date': occurred_at[:10] if occurred_at else '-',
            'occurred_at_label': occurred_at,
            'scope_label': self._scope_label(workflow_event, realtime_payload, target=target),
            'status_label': self._status_label(str(workflow_event.get('status') or '')),
            'entity_label': self._entity_label(workflow_event),
            'report_date': str(payload.get('report_date') or payload.get('business_date') or ''),
            'report_type_label': self._report_type_label(report_type),
            'published_shift_count': str(payload.get('published_shift_count') or 0),
            'exception_count': str(payload.get('exception_count') or 0),
            'reminder_reason': str(payload.get('reminder_reason') or ''),
            'tracking_card_no': str(payload.get('tracking_card_no') or realtime_payload.get('tracking_card_no') or ''),
        }

    def _scope_label(
        self,
        workflow_event: Mapping[str, Any],
        realtime_payload: Mapping[str, Any],
        *,
        target: WeComBotTarget,
    ) -> str:
        if target.target_type == 'team':
            return str(realtime_payload.get('team') or f"班组 #{target.target_key}")
        if target.target_type == 'workshop':
            return str(realtime_payload.get('workshop') or f"车间 #{target.target_key}")
        return '管理层播报'

    @staticmethod
    def _status_label(status: str) -> str:
        mapping = {
            'draft': '草稿',
            'submitted': '已提交',
            'reviewed': '已审核',
            'confirmed': '已确认',
            'published': '已发布',
        }
        return mapping.get(status, status or '-')

    @staticmethod
    def _event_label(event_type: str) -> str:
        mapping = {
            'attendance_confirmed': '考勤确认完成',
            'report_reviewed': '日报审核完成',
            'report_published': '日报发布完成',
            'entry_saved': '流程催报',
            'entry_submitted': '流程催报',
        }
        return mapping.get(event_type, event_type or '流程通知')

    @staticmethod
    def _entity_label(workflow_event: Mapping[str, Any]) -> str:
        entity_type = str(workflow_event.get('entity_type') or 'entity')
        entity_id = workflow_event.get('entity_id')
        return f'{entity_type} #{entity_id}' if entity_id is not None else entity_type

    @staticmethod
    def _report_type_label(report_type: str) -> str:
        mapping = {
            'production': '生产日报',
            'attendance': '考勤日报',
            'exception': '异常日报',
        }
        return mapping.get(report_type, report_type or '日报')

    @staticmethod
    def _format_datetime(value: Any) -> str:
        text = str(value or '').strip()
        if not text:
            return '-'
        try:
            return datetime.fromisoformat(text).strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return text

    @staticmethod
    def _normalize_optional_int(value: Any) -> int | None:
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _load_response_json(response) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _default_sender(*, url: str, json: dict[str, Any], timeout: float):
        return httpx.post(
            url,
            json=json,
            timeout=timeout,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )

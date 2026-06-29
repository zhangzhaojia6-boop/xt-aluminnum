from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.llm import LlmTextResponse
from app.config import Settings
from app.database import Base
from app.models.assistant_usage import AssistantUsage
from app.models.master import Workshop
from app.models.system import User
from app.schemas.assistant import AssistantQueryRequestIn
from app.services import assistant_service


def _settings() -> Settings:
    return Settings(
        APP_ENV='development',
        DATABASE_URL='sqlite:///:memory:',
        SECRET_KEY='s' * 32,
        INIT_ADMIN_PASSWORD='AdminPassword#2026',
        LLM_ENABLED=True,
        LLM_API_BASE='https://llm.example.invalid/v1',
        LLM_API_KEY='key',
        LLM_MODEL='deepseek-v3',
        LLM_DAILY_QUERY_LIMIT=2,
    )


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'assistant-usage.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, User.__table__, AssistantUsage.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    db = SessionLocal()
    user = User(username='manager', password_hash='x', name='Manager', role='manager', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return db, user


def test_assistant_query_records_llm_usage(tmp_path, monkeypatch) -> None:
    db, user = _session(tmp_path)
    captured = {}

    def fake_generate_llm_summary_with_usage(**kwargs):
        captured['messages'] = kwargs['messages']
        return LlmTextResponse(
            content=json.dumps(
                {
                    'summary': '真实 LLM 已生成回答。',
                    'cards': [{'title': '来源', 'summary': '来自当前数据中枢。', 'source_labels': ['数据中枢']}],
                    'next_actions': ['继续核实'],
                    'integrations_used': ['dashboard'],
                },
                ensure_ascii=False,
            ),
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            raw_usage={'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20},
        )

    monkeypatch.setattr(
        assistant_service,
        'generate_llm_summary_with_usage',
        fake_generate_llm_summary_with_usage,
    )

    response = assistant_service.run_assistant_query(
        AssistantQueryRequestIn(mode='answer', query='今天有什么异常', surface='review_home'),
        settings=_settings(),
        db=db,
        current_user=user,
    )

    usage = db.query(AssistantUsage).one()
    assert response.mock is False
    assert usage.user_id == user.id
    assert usage.input_tokens == 12
    assert usage.output_tokens == 8
    assert usage.total_tokens == 20
    prompt_text = '\n'.join(message['content'] for message in captured['messages'])
    assert '鑫泰铝业智能大脑' in prompt_text
    assert '鑫泰铝业协同平台' not in prompt_text
    assert '工厂多智能体助手' not in prompt_text


def test_assistant_query_enforces_daily_limit(tmp_path, monkeypatch) -> None:
    db, user = _session(tmp_path)
    db.add_all(
        [
            AssistantUsage(user_id=user.id, endpoint='query', model='deepseek-v3'),
            AssistantUsage(user_id=user.id, endpoint='query', model='deepseek-v3'),
        ]
    )
    db.commit()
    monkeypatch.setattr(
        assistant_service,
        'generate_llm_summary_with_usage',
        lambda **_kwargs: SimpleNamespace(content='should not call'),
    )

    with pytest.raises(HTTPException) as exc_info:
        assistant_service.run_assistant_query(
            AssistantQueryRequestIn(mode='answer', query='继续查', surface='review_home'),
            settings=_settings(),
            db=db,
            current_user=user,
        )

    assert exc_info.value.status_code == 429

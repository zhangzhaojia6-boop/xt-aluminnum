from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.validator import ValidatorAgent
from app.database import Base
from app.models.production import MobileShiftReport
from app.models.rule_config import RuleConfig
from app.rules.auto_confirm import evaluate_auto_confirm
from app.services import rule_config_service


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'validation-workshop-threshold.db'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def test_validation_uses_workshop_threshold_and_tags_rule(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    rule_config_service.invalidate_cache()
    with session_factory() as db:
        rule_config_service.set_threshold(
            db,
            scope_type='factory',
            scope_key=None,
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=30,
            updated_by=1,
        )
        rule_config_service.set_threshold(
            db,
            scope_type='workshop',
            scope_key='LZ01',
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=50,
            updated_by=1,
        )
        report_data = {
            'attendance_count': 10,
            'input_weight': 60.0,
            'output_weight': 51.0,
        }

        lz01 = evaluate_auto_confirm(report_data, workshop_code='LZ01', db=db)
        lz02 = evaluate_auto_confirm(report_data, workshop_code='LZ02', db=db)

    assert lz01.confirmed is False
    assert '[规则:MAX_SINGLE_SHIFT_WEIGHT@LZ01]' in lz01.validation.errors[0]
    assert lz02.confirmed is False
    assert '[规则:MAX_SINGLE_SHIFT_WEIGHT@factory]' in lz02.validation.errors[0]


def test_validator_returned_reason_includes_workshop_rule_tag(tmp_path, monkeypatch) -> None:
    session_factory = build_sessionmaker(tmp_path)
    rule_config_service.invalidate_cache()
    monkeypatch.setattr('app.services.pilot_observability_service.log_pilot_event', lambda *args, **kwargs: None)
    with session_factory() as db:
        rule_config_service.set_threshold(
            db,
            scope_type='workshop',
            scope_key='LZ01',
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=50,
            updated_by=1,
        )
        report = MobileShiftReport(
            id=101,
            business_date=date(2026, 5, 3),
            shift_config_id=1,
            workshop_id=1,
            report_status='submitted',
        )
        db.add(report)
        db.commit()

        decisions = ValidatorAgent().execute(
            db=db,
            report_id=101,
            workshop_code='LZ01',
            report_data={
                'attendance_count': 10,
                'input_weight': 60.0,
                'output_weight': 51.0,
            },
        )

    assert len(decisions) == 1
    assert report.report_status == 'returned'
    assert '[规则:MAX_SINGLE_SHIFT_WEIGHT@LZ01]' in (report.returned_reason or '')

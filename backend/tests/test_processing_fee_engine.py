"""Smoke tests for processing fee engine and profit snapshot agent."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.executive import (
    AluminumPriceDaily,
    MachineDailyCostSnapshot,
    MachineDailyProfitSnapshot,
    ProcessingFeeRule,
    ProcessingFeeSurcharge,
)
from app.services.processing_fee_service import (
    MissingFeeRuleError,
    quote_processing_fee,
)


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fee-engine.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            ProcessingFeeRule.__table__,
            ProcessingFeeSurcharge.__table__,
            AluminumPriceDaily.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def test_default_tier_simple_lookup(tmp_path):
    Session = build_session(tmp_path)
    with Session() as db:
        db.add(ProcessingFeeRule(
            customer_tier='default',
            alloy_grade='5052',
            process_type='hot_rolling',
            temper=None,
            thickness_min_mm=None,
            thickness_max_mm=None,
            fee_per_ton=Decimal('2600'),
            is_vat_inclusive=True,
            effective_from=date(2026, 1, 1),
        ))
        db.commit()

        quote = quote_processing_fee(
            db,
            customer_tier='default',
            alloy_grade='5052',
            process_type='hot_rolling',
            business_date=date(2026, 5, 1),
        )
        assert quote.base_fee == Decimal('2600')
        assert quote.total_fee == Decimal('2600')
        assert quote.surcharges == []
        assert quote.customer_tier == 'default'


def test_hengchang_thickness_range_and_surcharges(tmp_path):
    Session = build_session(tmp_path)
    with Session() as db:
        db.add(ProcessingFeeRule(
            customer_tier='hengchang',
            alloy_grade='6061',
            process_type='hot_rolling',
            temper='T6/T4',
            thickness_min_mm=Decimal('0.7'),
            thickness_max_mm=Decimal('0.8'),
            fee_per_ton=Decimal('6500'),
            is_vat_inclusive=True,
            effective_from=date(2026, 1, 1),
        ))
        db.add(ProcessingFeeSurcharge(
            customer_tier='hengchang',
            surcharge_type='thin_gauge',
            condition_json={'thickness_lt': 1.0},
            fee_per_ton=Decimal('300'),
            effective_from=date(2026, 1, 1),
            note='1mm 以下加 300',
        ))
        db.add(ProcessingFeeSurcharge(
            customer_tier='hengchang',
            surcharge_type='length',
            condition_json={'length_min': 5000, 'length_max': 5999},
            fee_per_ton=Decimal('200'),
            effective_from=date(2026, 1, 1),
        ))
        db.commit()

        quote = quote_processing_fee(
            db,
            customer_tier='hengchang',
            alloy_grade='6061',
            process_type='hot_rolling',
            temper='T6/T4',
            thickness_mm=0.75,
            length_mm=5200,
            business_date=date(2026, 5, 1),
        )
        assert quote.base_fee == Decimal('6500')
        surcharge_types = [s[0] for s in quote.surcharges]
        assert 'thin_gauge' in surcharge_types
        assert 'length' in surcharge_types
        assert quote.total_fee == Decimal('7000')  # 6500 + 300 + 200


def test_missing_rule_raises(tmp_path):
    Session = build_session(tmp_path)
    with Session() as db:
        with pytest.raises(MissingFeeRuleError) as exc:
            quote_processing_fee(
                db,
                customer_tier='default',
                alloy_grade='9999',
                process_type='hot_rolling',
                business_date=date(2026, 5, 1),
            )
        assert exc.value.reason == 'no_matching_base_rule'
        assert exc.value.spec['alloy_grade'] == '9999'


def test_thickness_out_of_range_rejects(tmp_path):
    Session = build_session(tmp_path)
    with Session() as db:
        db.add(ProcessingFeeRule(
            customer_tier='hengchang',
            alloy_grade='6061',
            process_type='hot_rolling',
            temper='T6/T4',
            thickness_min_mm=Decimal('4.5'),
            thickness_max_mm=Decimal('6.0'),
            fee_per_ton=Decimal('4500'),
            is_vat_inclusive=True,
            effective_from=date(2026, 1, 1),
        ))
        db.commit()

        with pytest.raises(MissingFeeRuleError):
            quote_processing_fee(
                db,
                customer_tier='hengchang',
                alloy_grade='6061',
                process_type='hot_rolling',
                temper='T6/T4',
                thickness_mm=1.0,
                business_date=date(2026, 5, 1),
            )

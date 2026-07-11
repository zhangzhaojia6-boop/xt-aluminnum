from datetime import date, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.mes import MesCoilSnapshot, MesStockRecord, MesWorkshopProcessRecord
from app.services.report import mes_factory_production_fact


BUSINESS_DATE = date(2026, 6, 18)


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-factory-production-fact.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            MesCoilSnapshot.__table__,
            MesStockRecord.__table__,
            MesWorkshopProcessRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _coil(
    *,
    source_id: str,
    create_date: str | None,
    current_workshop: str,
    feeding_weight: float,
    business_date: date | None = None,
    event_time: datetime | None = None,
) -> MesCoilSnapshot:
    metadata = {
        'CurrentWorkShop': current_workshop,
        'FeedingWeight': feeding_weight,
    }
    if create_date is not None:
        metadata['CreateDate'] = create_date
    return MesCoilSnapshot(
        coil_id=f'MES:{source_id}',
        tracking_card_no=source_id,
        current_workshop=current_workshop,
        feeding_weight=feeding_weight,
        business_date=business_date,
        event_time=event_time,
        source_payload={
            'metadata': metadata,
        },
    )


def test_factory_feeding_fact_uses_mes_product_create_date_and_current_workshop(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                _coil(source_id='before-boundary', create_date='2026-06-18 07:49:00', current_workshop='冷轧', feeding_weight=100),
                _coil(source_id='at-boundary', create_date='2026-06-18 07:50:00', current_workshop='冷轧', feeding_weight=200),
                _coil(source_id='after-boundary', create_date='2026-06-18 11:00:00', current_workshop='热轧', feeding_weight=227),
                _coil(source_id='no-workshop', create_date='2026-06-18 12:00:00', current_workshop='', feeding_weight=999),
            ]
        )
        db.commit()

    with session_factory() as db:
        fact = mes_factory_production_fact.build_factory_feeding_fact(db, target_date=BUSINESS_DATE)

    assert fact['source_table'] == 'MES_Product'
    assert fact['source_weight_field'] == 'FeedingWeight'
    assert fact['source_time_field'] == 'CreateDate'
    assert fact['source_pages'] == [
        {'page': '计划管理 / 投料管理', 'path': '/Feeding/Index'},
        {'page': '计划管理 / 随行卡管理', 'path': '/FollowCard/Index'},
    ]
    assert fact['business_day_start'] == '07:50'
    assert fact['factory_feeding_daily_input'] == 427.0
    assert fact['daily_row_count'] == 2
    assert fact['by_workshop'] == [
        {'workshop_name': '冷轧', 'business_day_start': '07:50', 'input': 200.0, 'row_count': 1},
        {'workshop_name': '热轧', 'business_day_start': '10:00', 'input': 227.0, 'row_count': 1},
    ]


def test_factory_feeding_rows_use_indexed_date_candidates_before_python_business_day_filter(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                _coil(
                    source_id='business-date-row',
                    create_date='2026-06-18 08:00:00',
                    current_workshop='冷轧',
                    feeding_weight=100,
                    business_date=BUSINESS_DATE,
                ),
                _coil(
                    source_id='event-time-row',
                    create_date=None,
                    current_workshop='热轧',
                    feeding_weight=125,
                    event_time=datetime(2026, 6, 18, 9, 0),
                ),
                _coil(
                    source_id='legacy-payload-only-row',
                    create_date='2026-06-18 10:00:00',
                    current_workshop='精整',
                    feeding_weight=225,
                ),
                _coil(
                    source_id='outside-row',
                    create_date='2026-06-01 08:00:00',
                    current_workshop='热轧',
                    feeding_weight=999,
                    business_date=date(2026, 6, 1),
                    event_time=datetime(2026, 6, 1, 8, 0),
                ),
            ]
        )
        db.commit()

    statements: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        if 'FROM mes_coil_snapshots' in statement:
            statements.append(statement)

    engine = session_factory.kw['bind']
    event.listen(engine, 'before_cursor_execute', capture_sql)
    try:
        with session_factory() as db:
            fact = mes_factory_production_fact.build_factory_feeding_fact(db, target_date=BUSINESS_DATE)
    finally:
        event.remove(engine, 'before_cursor_execute', capture_sql)

    assert fact['factory_feeding_daily_input'] == 325.0
    assert fact['daily_row_count'] == 2
    assert any('WHERE' in statement for statement in statements)
    assert any('business_date' in statement or 'event_time' in statement for statement in statements)


def test_factory_production_fact_does_not_report_yield_from_inbound_over_feeding(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                _coil(source_id='feeding-1', create_date='2026-06-18 08:00:00', current_workshop='冷轧', feeding_weight=100),
                MesStockRecord(
                    source_id='inbound-1',
                    source_path='sqlserver:stock_header_records',
                    net_weight_tons=85,
                    business_date=BUSINESS_DATE,
                    source_payload={'InStockDate': '2026-06-18 10:00:00', 'TotalNetWeight': '85000'},
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-1',
                    source_path='sqlserver:workshop_process_records',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=66,
                    business_date=BUSINESS_DATE,
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        fact = mes_factory_production_fact.build_factory_production_fact(db, target_date=BUSINESS_DATE)

    assert fact['factory_feeding_daily_input'] == 100.0
    assert fact['factory_packaging_daily_output'] == 66.0
    assert fact['factory_finished_inbound_daily_output'] == 85.0
    assert fact['daily_yield_rate'] is None
    assert fact['month_yield_rate'] is None
    assert fact['yield_rate_source'] == 'unavailable_requires_same_basis'
    assert fact['feeding_daily_delta'] is None
    assert fact['feeding_month_to_date_delta'] is None
    assert fact['feeding_source_pages'] == [
        {'page': '计划管理 / 投料管理', 'path': '/Feeding/Index'},
        {'page': '计划管理 / 随行卡管理', 'path': '/FollowCard/Index'},
    ]


def test_factory_production_fact_returns_null_yield_when_feeding_is_zero(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesStockRecord(
                source_id='inbound-without-feeding',
                source_path='sqlserver:stock_header_records',
                net_weight_tons=85,
                business_date=BUSINESS_DATE,
            )
        )
        db.commit()

    with session_factory() as db:
        fact = mes_factory_production_fact.build_factory_production_fact(db, target_date=BUSINESS_DATE)

    assert fact['factory_feeding_daily_input'] == 0.0
    assert fact['daily_yield_rate'] is None


def test_reconciliation_leaves_mes_home_reference_empty_without_hardcoded_manual_values(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                _coil(source_id='month-before', create_date='2026-06-01 10:00:00', current_workshop='热轧', feeding_weight=5953),
                _coil(source_id='daily-1', create_date='2026-06-18 08:00:00', current_workshop='冷轧', feeding_weight=200),
                _coil(source_id='daily-2', create_date='2026-06-18 10:00:00', current_workshop='热轧', feeding_weight=227),
                MesWorkshopProcessRecord(
                    source_id='pkg-jz',
                    source_path='sqlserver:workshop_process_records',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=66.1,
                    business_date=BUSINESS_DATE,
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        payload = mes_factory_production_fact.build_factory_production_reconciliation(db, target_date=BUSINESS_DATE)

    assert payload['factory_feeding_daily_input'] == 427.0
    assert payload['factory_feeding_month_to_date_input'] == 6380.0
    assert payload['mes_home_reference'] == {}
    assert payload['mes_home_reference_source'] == 'unavailable'
    assert payload['feeding_daily_delta'] is None
    assert payload['feeding_month_to_date_delta'] is None
    assert payload['finishing_packaging_daily_delta'] is None
    assert payload['source_mapping']['mes_feeding_management']['endpoint'] == '/Feeding/Index'
    assert payload['source_mapping']['mes_follow_card_management']['endpoint'] == '/FollowCard/Index'

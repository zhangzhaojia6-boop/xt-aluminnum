from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import HermesKnowledgeUnit
from app.models.master import Team, Workshop
from app.models.rag import RagDocument
from app.models.system import User
from app.services.hermes_rag_router_service import route_knowledge_request


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            RagDocument.__table__,
            HermesKnowledgeUnit.__table__,
        ],
    )
    return Session(engine)


def test_routes_2050_electricity_question_to_metric_process_case_units() -> None:
    db = _db()
    db.add_all(
        [
            HermesKnowledgeUnit(
                unit_key='metric-electricity-per-ton',
                layer='field',
                unit_type='metric',
                title='吨电耗定义',
                content='吨电耗 = 用电量 / 对应产量。',
                status='active',
            ),
            HermesKnowledgeUnit(
                unit_key='process-cold-rolling',
                layer='general_industry',
                unit_type='process',
                title='冷轧工艺',
                content='冷轧会受压下率、道次、退火状态影响。',
                status='active',
            ),
            HermesKnowledgeUnit(
                unit_key='case-2050-high-energy',
                layer='site_case',
                unit_type='case',
                title='2050 吨电耗异常案例',
                content='2050 吨电耗异常时先核对产量分母、开机时间和停机说明。',
                status='active',
            ),
        ]
    )
    db.commit()

    result = route_knowledge_request(db, query='2050 今天吨电耗为什么高？', business_date=date(2026, 6, 25))

    assert result.domain == 'process_quality'
    assert result.object_key == '2050'
    assert result.metric == 'electricity_per_ton'
    assert [item.unit_type for item in result.units] == ['metric', 'process', 'case']


def test_daily_dynamic_numbers_are_not_returned_as_knowledge() -> None:
    db = _db()
    db.add(
        HermesKnowledgeUnit(
            unit_key='bad-daily-number',
            layer='site_case',
            unit_type='daily_fact',
            title='6月19日总产量',
            content='6月19日总产量 366 吨。',
            status='active',
        )
    )
    db.commit()

    result = route_knowledge_request(db, query='今天总产量是多少？', business_date=date(2026, 6, 25))

    assert result.units == []
    assert result.excluded_units[0].unit_type == 'daily_fact'

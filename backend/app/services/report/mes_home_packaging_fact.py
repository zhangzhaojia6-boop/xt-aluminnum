from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.report.mes_factory_packaging_fact import (
    BUSINESS_DAY_START_LABEL,
    FACT_PROCESS_FIELD,
    FACT_PROJECTION_DATE_FIELD,
    FACT_PROJECTION_TABLE,
    FACT_PROJECTION_TIME_FIELD,
    FACT_PROJECTION_WEIGHT_FIELD,
    FACT_SOURCE_PATH,
    FACT_SOURCE_TABLE,
    FACT_TIME_FIELD,
    FACT_WEIGHT_FIELD,
    FACT_WORKSHOP_FIELD,
    PACKAGING_PROCESS_KEYWORD,
    WORKSHOP_ALIAS_MAP,
    build_factory_packaging_fact,
    build_factory_packaging_reconciliation,
)


MES_HOME_SOURCE_PATH = FACT_SOURCE_PATH
MES_HOME_SOURCE_TABLE = FACT_SOURCE_TABLE
MES_HOME_WEIGHT_FIELD = FACT_WEIGHT_FIELD
MES_HOME_TIME_FIELD = FACT_TIME_FIELD
MES_HOME_PROJECTION_TABLE = FACT_PROJECTION_TABLE
BUSINESS_DAY_START = BUSINESS_DAY_START_LABEL


def build_mes_home_packaging_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    return build_factory_packaging_fact(db, target_date=target_date)


def build_mes_home_reconciliation(db: Session, *, target_date: date) -> dict[str, Any]:
    return build_factory_packaging_reconciliation(db, target_date=target_date)


__all__ = [
    'BUSINESS_DAY_START',
    'FACT_PROCESS_FIELD',
    'FACT_PROJECTION_DATE_FIELD',
    'FACT_PROJECTION_TIME_FIELD',
    'FACT_PROJECTION_WEIGHT_FIELD',
    'FACT_WORKSHOP_FIELD',
    'MES_HOME_PROJECTION_TABLE',
    'MES_HOME_SOURCE_PATH',
    'MES_HOME_SOURCE_TABLE',
    'MES_HOME_TIME_FIELD',
    'MES_HOME_WEIGHT_FIELD',
    'PACKAGING_PROCESS_KEYWORD',
    'WORKSHOP_ALIAS_MAP',
    'build_mes_home_packaging_fact',
    'build_mes_home_reconciliation',
]

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(settings.DATABASE_URL, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, future=True)


# Lazy compatibility aliases for scripts/imports.
engine = None
SessionLocal = None


def _ensure_compat_aliases() -> None:
    global engine, SessionLocal
    if engine is None:
        engine = get_engine()
    if SessionLocal is None:
        SessionLocal = get_sessionmaker()


def get_db():
    _ensure_compat_aliases()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

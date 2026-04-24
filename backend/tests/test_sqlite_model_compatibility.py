from sqlalchemy import create_engine

from app.models import Base


def test_models_can_create_all_on_sqlite() -> None:
    engine = create_engine('sqlite:///:memory:', future=True)

    Base.metadata.create_all(bind=engine)

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.mes import MesMaterialRecord, MesWorkshopProcessRecord
from app.services import mes_extended_service


def test_mes_extended_records_can_be_limited_to_workshop_names(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-extended-scope.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesMaterialRecord.__table__, MesWorkshopProcessRecord.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    target = date(2026, 6, 1)
    db.add_all([
        MesWorkshopProcessRecord(
            source_id='process-zx-1',
            source_path='process',
            workshop_name='新厂在线车间',
            process_name='北线退火',
            business_date=target,
        ),
        MesWorkshopProcessRecord(
            source_id='process-jz-1',
            source_path='process',
            workshop_name='精整',
            process_name='剪切',
            business_date=target,
        ),
        MesMaterialRecord(
            source_id='material-zx-1',
            source_path='material',
            material_code='A',
            workshop_name='新厂在线车间',
            line_name='北线',
            business_date=target,
            weight_tons=12.5,
        ),
        MesMaterialRecord(
            source_id='material-jz-1',
            source_path='material',
            material_code='B',
            workshop_name='精整',
            line_name='纵剪',
            business_date=target,
            weight_tons=8.0,
        ),
    ])
    db.commit()

    process_rows = mes_extended_service.list_workshop_process_records(
        db,
        business_date=target,
        workshop_names={'新厂在线车间'},
    )
    material_rows = mes_extended_service.list_material_records(
        db,
        business_date=target,
        workshop_names={'新厂在线车间'},
    )

    assert [row['workshop_name'] for row in process_rows] == ['新厂在线车间']
    assert [row['workshop_name'] for row in material_rows] == ['新厂在线车间']

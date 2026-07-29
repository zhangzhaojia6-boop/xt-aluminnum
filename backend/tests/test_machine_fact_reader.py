from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.master import Equipment, Workshop
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.agent_command_service import read_machine_facts


class _MesReader:
    def read_sources(self, *, business_date, query_keys):
        assert business_date == date(2026, 7, 21)
        assert query_keys == ["workshop_process_records"]
        return {
            "business_date": business_date.isoformat(),
            "records": {
                "workshop_process_records": [
                    {
                        "source_id": "mes-process-rz2-20260721",
                        "source_path": "sqlserver:workshop_process_records",
                        "event_time": "2026-07-21T13:15:00+08:00",
                        "metadata": {
                            "DeviceName": "2号机",
                            "WorkShopName": "热轧车间",
                            "ProcessName": "热轧",
                            "BeginDatetime": "2026-07-21T08:00:00+08:00",
                            "EndDatetime": "2026-07-21T12:30:00+08:00",
                            "WorkerName": "不应出现在回答中",
                        },
                    }
                ]
            },
            "source_status": {
                "mes": "ok",
                "sources": {"workshop_process_records": {"status": "ok", "count": 1}},
            },
            "source_errors": {},
        }


class _WrongMachineMesReader(_MesReader):
    def read_sources(self, *, business_date, query_keys):
        payload = super().read_sources(
            business_date=business_date,
            query_keys=query_keys,
        )
        record = payload["records"]["workshop_process_records"][0]
        record["metadata"]["DeviceName"] = "12号机"
        return payload


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _root_owner() -> User:
    return User(
        id=1,
        username="root-owner-machine-fact",
        password_hash="x",
        name="管理员",
        role="admin",
        is_active=True,
    )


def test_machine_operation_prefers_direct_mes_reader_and_preserves_semantics() -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()
    try:
        facts = read_machine_facts(
            db,
            intent="machine_operation",
            business_date=date(2026, 7, 21),
            command_text="7月21日2号机几点开几点停",
            current_user=db.get(User, 1),
            mes_reader=_MesReader(),
        )

        assert facts["record_count"] == 1
        assert facts["fact_status"] == "confirmed"
        assert facts["complete_record_count"] == 1
        assert facts["data_source"] == "mes_readonly"
        assert facts["record_semantics"] == "mes_process_start_end_not_physical_power"
        assert facts["top_operations"][0]["begin_at"].endswith("08:00:00+08:00")
        assert facts["top_operations"][0]["end_at"].endswith("12:30:00+08:00")
        assert facts["top_operations"][0]["elapsed_minutes"] == 270
        assert (
            facts["top_operations"][0]["trace_id"]
            == "mes-process:mes-process-rz2-20260721"
        )
        assert "不应出现在回答中" not in repr(facts)
    finally:
        db.close()


def test_machine_operation_filter_does_not_mix_2_and_12() -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()
    try:
        facts = read_machine_facts(
            db,
            intent="machine_operation",
            business_date=date(2026, 7, 21),
            command_text="7月21日2号机几点开几点停",
            current_user=db.get(User, 1),
            mes_reader=_WrongMachineMesReader(),
        )

        assert facts["record_count"] == 0
        assert facts["fact_status"] == "missing"
    finally:
        db.close()


def test_machine_stop_reads_structured_owner_daily_supplement() -> None:
    db = _db_session()
    db.add(_root_owner())
    db.add(
        WorkOrder(
            id=11,
            tracking_card_no="OWNER-overhaul_owner-9-2026-07-21",
            process_route_code="owner_daily",
            overall_status="active",
        )
    )
    db.add(
        WorkOrderEntry(
            id=12,
            work_order_id=11,
            workshop_id=1,
            business_date=date(2026, 7, 21),
            entry_type="owner_daily",
            entry_status="submitted",
            extra_payload={
                "machine_stop_records": [
                    {
                        "workshop_name": "热轧车间",
                        "machine_name": "2号机",
                        "shift_name": "白班",
                        "downtime_minutes": 42,
                        "downtime_reason": "换辊待维修确认",
                    },
                    {
                        "workshop_name": "热轧车间",
                        "machine_name": "2号机",
                        "shift_name": "夜班",
                        "downtime_minutes": 42,
                        "downtime_reason": "换辊待维修确认",
                    }
                ]
            },
        )
    )
    db.commit()
    try:
        facts = read_machine_facts(
            db,
            intent="machine_stop",
            business_date=date(2026, 7, 21),
            command_text="2号机为什么停",
            current_user=db.get(User, 1),
        )

        assert facts["stop_count"] == 2
        assert facts["fact_status"] == "confirmed"
        assert facts["total_downtime_minutes"] == 84
        assert facts["top_stops"][0]["equipment_name"] == "2号机"
        assert facts["top_stops"][0]["downtime_reason"] == "换辊待维修确认"
        assert facts["top_stops"][0]["data_source"] == "owner_daily_machine_stop"
    finally:
        db.close()


def test_owner_daily_stop_enriches_matching_shift_row_without_double_counting() -> None:
    db = _db_session()
    db.add(_root_owner())
    db.add(
        Workshop(
            id=1,
            code="RZ",
            name="热轧车间",
            workshop_type="rolling",
            sort_order=1,
            is_active=True,
        )
    )
    db.add(
        Equipment(
            id=2,
            code="RZ-2",
            name="2号机",
            workshop_id=1,
            is_active=True,
        )
    )
    db.add(
        ShiftConfig(
            id=3,
            code="DAY",
            name="白班",
            shift_type="day",
            start_time=time(8, 0),
            end_time=time(20, 0),
            workshop_id=1,
            is_active=True,
        )
    )
    db.add(
        ShiftProductionData(
            id=4,
            business_date=date(2026, 7, 21),
            shift_config_id=3,
            workshop_id=1,
            equipment_id=2,
            downtime_minutes=42,
            downtime_reason=None,
            data_source="mobile",
            data_status="confirmed",
        )
    )
    db.add(
        WorkOrder(
            id=11,
            tracking_card_no="OWNER-overhaul_owner-9-2026-07-21",
            process_route_code="owner_daily",
            overall_status="active",
        )
    )
    db.add(
        WorkOrderEntry(
            id=12,
            work_order_id=11,
            workshop_id=1,
            business_date=date(2026, 7, 21),
            entry_type="owner_daily",
            entry_status="submitted",
            extra_payload={
                "machine_stop_records": [
                    {
                        "workshop_name": "热轧车间",
                        "machine_name": "2号机",
                        "shift_name": "白班",
                        "downtime_minutes": 42,
                        "downtime_reason": "换辊待维修确认",
                    }
                ]
            },
        )
    )
    db.commit()
    try:
        facts = read_machine_facts(
            db,
            intent="machine_stop",
            business_date=date(2026, 7, 21),
            command_text="2号机为什么停",
            current_user=db.get(User, 1),
        )

        assert facts["stop_count"] == 1
        assert facts["fact_status"] == "confirmed"
        assert facts["total_downtime_minutes"] == 42
        assert facts["top_stops"][0]["downtime_reason"] == "换辊待维修确认"
        assert facts["top_stops"][0]["data_source"] == "mobile+owner_daily_machine_stop"
    finally:
        db.close()

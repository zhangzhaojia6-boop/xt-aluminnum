from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.iot_energy_adapter import IotEnergyReading, SqlServerIotEnergyAdapter, _ensure_read_only_query
from app.config import Settings
from app.database import Base
from app.models.energy import IotEnergySnapshot, IotEnergySyncRun
from app.models.master import Equipment, Workshop
from app.services.iot_energy_sync_service import get_iot_energy_adapter_for_settings, sync_iot_energy_snapshots


class FakeIotEnergyAdapter:
    def __init__(self, readings):
        self.readings = readings

    def list_readings(self, *, business_date, limit=500):
        self.business_date = business_date
        self.limit = limit
        return list(self.readings)


class FlakyIotEnergyAdapter:
    def __init__(self, *, fail_times, readings):
        self.fail_times = fail_times
        self.readings = readings
        self.calls = 0

    def list_readings(self, *, business_date, limit=500):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError('temporary iot outage secret=hidden')
        return list(self.readings)


def _make_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def test_iot_energy_sync_writes_shadow_rows_with_meter_mapping() -> None:
    db = _make_session()
    try:
        db.add(Workshop(id=1, code='LJ', name='拉矫车间'))
        db.add(Equipment(id=10, code='LJ-01', name='拉矫 1#', workshop_id=1))
        db.commit()

        adapter = FakeIotEnergyAdapter([
            IotEnergyReading(
                meter_code='M-LJ-01',
                meter_name='拉矫一线电表',
                reading_at=datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc),
                electricity_kwh=123.4,
                gas_m3=5.0,
                water_m3=1.2,
                metadata={'raw_id': 'iot-001'},
            )
        ])

        result = sync_iot_energy_snapshots(
            db,
            business_date=date(2026, 6, 11),
            adapter=adapter,
            meter_map={'M-LJ-01': {'workshop_code': 'LJ', 'machine_code': 'LJ-01'}},
        )

        assert result.status == 'success'
        assert result.records_read == 1
        assert result.records_written == 1

        run = db.query(IotEnergySyncRun).one()
        assert run.status == 'success'
        assert run.records_read == 1
        assert run.records_written == 1

        snapshot = db.query(IotEnergySnapshot).one()
        assert snapshot.sync_run_id == run.id
        assert snapshot.business_date == date(2026, 6, 11)
        assert snapshot.workshop_id == 1
        assert snapshot.machine_id == 10
        assert snapshot.meter_code == 'M-LJ-01'
        assert float(snapshot.electricity_kwh) == 123.4
        assert snapshot.raw_payload['raw_id'] == 'iot-001'
    finally:
        db.close()


def test_iot_energy_sync_is_safe_when_adapter_is_missing() -> None:
    db = _make_session()
    try:
        result = sync_iot_energy_snapshots(db, business_date=date(2026, 6, 11), adapter=None)

        assert result.status == 'skipped'
        assert result.records_read == 0
        assert result.records_written == 0
        assert '未配置' in (result.error_message or '')
        assert db.query(IotEnergySnapshot).count() == 0
        assert db.query(IotEnergySyncRun).one().status == 'skipped'
    finally:
        db.close()


def test_iot_energy_sync_retries_transient_adapter_failures() -> None:
    db = _make_session()
    try:
        adapter = FlakyIotEnergyAdapter(
            fail_times=1,
            readings=[
                IotEnergyReading(
                    meter_code='M-LJ-01',
                    reading_at=datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc),
                    electricity_kwh=10.0,
                )
            ],
        )

        result = sync_iot_energy_snapshots(
            db,
            business_date=date(2026, 6, 11),
            adapter=adapter,
            retry_limit=1,
            retry_backoff_seconds=0,
        )

        assert result.status == 'success'
        assert result.attempt_count == 2
        assert adapter.calls == 2
        assert db.query(IotEnergySnapshot).count() == 1
        run = db.query(IotEnergySyncRun).one()
        assert run.status == 'success'
        assert run.raw_payload['attempt_count'] == 2
        assert 'secret=hidden' not in repr(run.raw_payload)
    finally:
        db.close()


def test_iot_energy_adapter_rejects_write_sql() -> None:
    _ensure_read_only_query('SELECT TOP (10) * FROM MeterReadings')
    with pytest.raises(ValueError):
        _ensure_read_only_query('UPDATE MeterReadings SET value = 0')


def test_iot_energy_adapter_factory_uses_sqlserver_settings() -> None:
    runtime = Settings(
        _env_file=None,
        IOT_ENERGY_ADAPTER='sqlserver',
        IOT_ENERGY_SQLSERVER_HOST='127.0.0.1',
        IOT_ENERGY_SQLSERVER_DATABASE='iot',
        IOT_ENERGY_SQLSERVER_USERNAME='reader',
        IOT_ENERGY_SQLSERVER_PASSWORD='secret',
        IOT_ENERGY_SQLSERVER_QUERY='SELECT TOP ({limit}) * FROM MeterReadings WHERE BusinessDate = %s',
    )

    adapter = get_iot_energy_adapter_for_settings(runtime)

    assert isinstance(adapter, SqlServerIotEnergyAdapter)
    assert runtime.iot_energy_meter_map == {}


def test_iot_energy_sqlserver_config_requires_connection_and_query_in_production() -> None:
    runtime = Settings(
        _env_file=None,
        APP_ENV='production',
        SECRET_KEY='x' * 40,
        INIT_ADMIN_PASSWORD='StrongAdmin#2026',
        IOT_ENERGY_ADAPTER='sqlserver',
        IOT_ENERGY_SQLSERVER_HOST='',
        IOT_ENERGY_SQLSERVER_DATABASE='',
        IOT_ENERGY_SQLSERVER_USERNAME='',
        IOT_ENERGY_SQLSERVER_PASSWORD='',
        IOT_ENERGY_SQLSERVER_QUERY='',
    )

    with pytest.raises(RuntimeError) as exc_info:
        runtime.validate_runtime_settings()

    message = str(exc_info.value)
    assert 'IOT_ENERGY_ADAPTER=sqlserver is missing' in message
    assert 'IOT_ENERGY_SQLSERVER_HOST' in message
    assert 'IOT_ENERGY_SQLSERVER_QUERY' in message

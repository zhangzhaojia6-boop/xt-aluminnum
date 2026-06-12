from datetime import date, datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.adapters.iot_energy_adapter import IotEnergyReading
from app.config import Settings


MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'check_iot_energy_preflight.py'
SPEC = spec_from_file_location('check_iot_energy_preflight', MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FakeAdapter:
    def __init__(self, readings):
        self.readings = readings
        self.calls = []

    def list_readings(self, *, business_date, limit=500):
        self.calls.append({'business_date': business_date, 'limit': limit})
        return list(self.readings)


def test_iot_energy_preflight_skips_when_adapter_is_not_configured() -> None:
    payload = MODULE.inspect_iot_energy_preflight(
        runtime_settings=Settings(_env_file=None, IOT_ENERGY_ADAPTER='null'),
        adapter_factory=lambda _settings: None,
        target_date=date(2026, 6, 11),
    )

    assert payload['adapter'] == 'null'
    assert payload['configured'] is False
    assert payload['connection']['status'] == 'skipped'
    assert payload['readings']['count'] == 0
    assert payload['readiness']['ready'] is False
    assert 'IOT_ENERGY_ADAPTER' in payload['readiness']['required_env']
    assert '配置物联网能耗只读连接' in payload['readiness']['next_actions']


def test_iot_energy_preflight_reports_missing_sqlserver_config_before_connecting() -> None:
    payload = MODULE.inspect_iot_energy_preflight(
        runtime_settings=Settings(
            _env_file=None,
            IOT_ENERGY_ADAPTER='sqlserver',
            IOT_ENERGY_SQLSERVER_HOST='',
            IOT_ENERGY_SQLSERVER_DATABASE='',
            IOT_ENERGY_SQLSERVER_USERNAME='',
            IOT_ENERGY_SQLSERVER_PASSWORD='',
            IOT_ENERGY_SQLSERVER_QUERY='',
            IOT_ENERGY_METER_MAP='{}',
        ),
        adapter_factory=lambda _settings: None,
        target_date=date(2026, 6, 11),
    )

    assert payload['configured'] is True
    assert payload['connection']['status'] == 'skipped'
    assert payload['connection']['reason'] == 'missing_sqlserver_config'
    assert payload['readiness']['ready'] is False
    assert payload['readiness']['required_env'] == [
        'IOT_ENERGY_SQLSERVER_HOST',
        'IOT_ENERGY_SQLSERVER_DATABASE',
        'IOT_ENERGY_SQLSERVER_USERNAME',
        'IOT_ENERGY_SQLSERVER_PASSWORD',
        'IOT_ENERGY_SQLSERVER_QUERY',
        'IOT_ENERGY_METER_MAP',
    ]
    assert '补齐物联网数据库地址、库名、只读账号和查询 SQL' in payload['readiness']['next_actions']
    assert '补齐表计/点位到车间、机列的映射' in payload['readiness']['next_actions']


def test_iot_energy_preflight_summarizes_readings_and_mapping_gaps() -> None:
    adapter = FakeAdapter([
        IotEnergyReading(
            meter_code='M-LJ-01',
            meter_name='拉矫一线电表',
            reading_at=datetime(2026, 6, 11, 9, 20, tzinfo=timezone.utc),
            electricity_kwh=120.5,
            gas_m3=3.2,
            metadata={'password': 'should-not-print', 'raw_id': 'iot-1'},
        ),
        IotEnergyReading(
            meter_code='M-UNKNOWN',
            meter_name='未映射电表',
            reading_at=datetime(2026, 6, 11, 9, 25, tzinfo=timezone.utc),
            water_m3=8.0,
        ),
    ])
    runtime = Settings(
        _env_file=None,
        IOT_ENERGY_ADAPTER='sqlserver',
        IOT_ENERGY_SQLSERVER_HOST='127.0.0.1',
        IOT_ENERGY_SQLSERVER_DATABASE='iot',
        IOT_ENERGY_SQLSERVER_USERNAME='reader',
        IOT_ENERGY_SQLSERVER_PASSWORD='secret',
        IOT_ENERGY_SQLSERVER_QUERY='SELECT TOP ({limit}) * FROM MeterReadings WHERE BusinessDate = %s',
        IOT_ENERGY_METER_MAP='{"M-LJ-01":{"workshop_code":"LJ","machine_code":"LJ-01"}}',
    )

    payload = MODULE.inspect_iot_energy_preflight(
        runtime_settings=runtime,
        adapter_factory=lambda _settings: adapter,
        target_date=date(2026, 6, 11),
        limit=10,
    )

    assert payload['adapter'] == 'sqlserver'
    assert payload['configured'] is True
    assert payload['connection']['status'] == 'success'
    assert payload['readings']['count'] == 2
    assert payload['readings']['meters_with_mapping'] == 1
    assert payload['readings']['meters_missing_mapping'] == ['M-UNKNOWN']
    assert payload['readings']['totals']['electricity_kwh'] == 120.5
    assert payload['readings']['totals']['gas_m3'] == 3.2
    assert payload['readings']['totals']['water_m3'] == 8.0
    assert payload['readings']['items'][0]['mapping_status'] == 'mapped'
    assert payload['readings']['items'][1]['mapping_status'] == 'missing_mapping'
    assert payload['readiness']['ready'] is False
    assert payload['readiness']['required_env'] == []
    assert payload['readiness']['next_actions'] == ['补齐未映射表计：M-UNKNOWN']
    assert adapter.calls == [{'business_date': date(2026, 6, 11), 'limit': 10}]
    assert 'secret' not in repr(payload)
    assert 'should-not-print' not in repr(payload)

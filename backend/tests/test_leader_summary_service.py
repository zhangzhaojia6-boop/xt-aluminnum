from __future__ import annotations

from datetime import date

from app.config import Settings
from app.services import leader_summary_service


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f'http_{self.status_code}')

    def json(self) -> dict:
        return self._body


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    def post(self, *_args, **_kwargs):
        return self._response


def _build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'LLM_ENABLED': False,
    }
    values.update(overrides)
    return Settings(**values)


def _sample_report_data() -> dict:
    return {
        'total_output_weight': 180.5,
        'total_energy': 320.3,
        'energy_per_ton': 1.77,
        'reporting_rate': 96.2,
        'total_attendance': 42,
        'contract_lane': {'daily_contract_weight': 195.0},
        'yield_matrix_lane': {'company_total_yield': 94.4, 'quality_status': 'ready'},
        'anomaly_summary': {'total': 2, 'digest': '班次缺报 1条；出勤异常 1条'},
        'inventory_lane': [
            {'storage_prepared': 12.5, 'storage_finished': 8.0, 'shipment_weight': 5.0, 'storage_inbound_area': 1200.0},
            {'storage_prepared': 6.5, 'storage_finished': 4.0, 'shipment_weight': 3.0, 'storage_inbound_area': 800.0},
        ],
    }


def test_build_best_effort_leader_summary_returns_deterministic_fallback_when_llm_disabled() -> None:
    payload = leader_summary_service.build_best_effort_leader_summary(
        report_date=date(2026, 4, 10),
        report_data=_sample_report_data(),
        settings=_build_settings(LLM_ENABLED=False),
    )

    assert payload['summary_source'] == 'deterministic'
    assert '今日产量 180.50 吨' in payload['summary_text']
    assert '发货 8.00 吨' in payload['summary_text']
    assert '入库面积 2000.00 ㎡' in payload['summary_text']
    assert payload['metrics']['yield_rate'] == 94.4
    assert payload['metrics']['shipment_weight'] == 8.0
    assert payload['metrics']['storage_inbound_area'] == 2000.0


def test_build_best_effort_leader_summary_prefers_llm_when_available() -> None:
    payload = leader_summary_service.build_best_effort_leader_summary(
        report_date=date(2026, 4, 10),
        report_data=_sample_report_data(),
        settings=_build_settings(
            LLM_ENABLED=True,
            LLM_API_BASE='https://example.invalid/v1',
            LLM_API_KEY='llm-key',
            LLM_MODEL='gpt-5.4-mini',
        ),
        llm_client=_FakeClient(
            _FakeResponse(body={'choices': [{'message': {'content': '这是 LLM 生成的领导摘要。'}}]})
        ),
    )

    assert payload['summary_source'] == 'llm'
    assert payload['summary_text'] == '这是 LLM 生成的领导摘要。'
    assert payload['llm_error'] is None

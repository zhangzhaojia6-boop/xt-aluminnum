from app.main import app


def test_mobile_routes_are_registered() -> None:
    assert app.url_path_for('mobile-current-shift') == '/api/v1/mobile/current-shift'
    assert app.url_path_for('mobile-report-detail', business_date='2026-03-27', shift_id='1') == '/api/v1/mobile/report/2026-03-27/1'
    assert app.url_path_for('mobile-report-save') == '/api/v1/mobile/report/save'
    assert app.url_path_for('mobile-report-submit') == '/api/v1/mobile/report/submit'
    assert app.url_path_for('mobile-report-history') == '/api/v1/mobile/report/history'

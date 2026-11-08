import csv
import io

import pytest

from app.domain import procurement_flow as flow
from app.models.procurement import ProcurementRequest, ProcurementSupplier
from app.models.system import AuditLog
from app.services import procurement_admin_service as admin_service
from app.services import procurement_service as service
from tests.test_procurement_flow import (  # noqa: F401
    ROLES, act, as_user, client, db, new_request, person, to_contract, to_quotation,
)


def quote(db, request, *names, price=100):
    quotes = [{'supplier': name, 'unit_price': price + index} for index, name in enumerate(names)]
    return act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=quotes, selected_index=0)


def test_gate_sees_only_requests_it_handles(db, client):
    request = new_request(db)
    db.commit()
    gate = ROLES['gate']
    as_user(db, gate)
    assert client.get(f'/api/v1/procurement/requests/{request.id}').status_code == 403
    assert client.get('/api/v1/procurement/board').status_code == 403
    assert client.get('/api/v1/procurement/ledger').status_code == 403
    assert client.get('/api/v1/procurement/ledger.csv').status_code == 403
    assert client.get('/api/v1/procurement/suppliers').status_code == 403
    assert client.get('/api/v1/procurement/requests?scope=all').status_code == 403
    assert client.get('/api/v1/procurement/meta').json()['can_view_all'] is False

    request.current_step = 'gate_registration'
    db.commit()
    assert client.get(f'/api/v1/procurement/requests/{request.id}').status_code == 200
    act(db, request, gate, 'register', supplier='甲', goods='轴承', quantity='1', plate_no='豫A1')
    db.commit()
    assert request.current_step == 'acceptance'
    assert client.get(f'/api/v1/procurement/requests/{request.id}').status_code == 200


@pytest.mark.parametrize('role', [flow.ROLE_WAREHOUSE, flow.ROLE_QUALITY, flow.ROLE_EQUIPMENT, flow.ROLE_ACCOUNTANT])
def test_operational_roles_cannot_view_all(db, role):
    user = person(db, ROLES[role])
    assert service.can_view_all(user, service.user_roles(db, user)) is False


@pytest.mark.parametrize('role', sorted(flow.VIEW_ALL_ROLES))
def test_management_roles_can_view_all(db, role):
    user = person(db, ROLES[role])
    assert service.can_view_all(user, service.user_roles(db, user)) is True


def test_audit_reads_everything_but_cannot_act(db, client):
    request = new_request(db)
    act(db, request, 1, 'submit')
    db.commit()
    as_user(db, ROLES['audit'])
    assert client.get('/api/v1/procurement/ledger').json()['total'] == 1
    result = client.post(f'/api/v1/procurement/requests/{request.id}/actions', json={'action': 'approve', 'expected_step': 'workshop_approval'})
    assert result.status_code == 403
    assert client.post(f'/api/v1/procurement/requests/{request.id}/void', json={'reason': '查'}).status_code == 403
    assert client.post('/api/v1/procurement/suppliers', json={'name': '甲'}).status_code == 403


def test_ledger_filters_pages_and_totals(db):
    audit = person(db, ROLES['audit'])
    for index in range(3):
        new_request(db, quantity=str(index + 1), price='100')
    other = new_request(db, category='劳保用品', emergency=True)
    db.flush()
    result = admin_service.ledger(db, user=audit, filters={}, page=1, page_size=2)
    assert result['total'] == 4
    assert len(result['items']) == 2
    assert result['total_amount'] == '2600.00'
    assert result['items'][0]['id'] == other.id
    assert result['items'][0]['requester_name'] == '统计员'
    assert admin_service.ledger(db, user=audit, filters={'category': '劳保用品'})['total'] == 1
    assert admin_service.ledger(db, user=audit, filters={'emergency': True})['total'] == 1
    assert admin_service.ledger(db, user=audit, filters={'emergency': False})['total'] == 3
    assert admin_service.ledger(db, user=audit, filters={'keyword': '6205'})['total'] == 4
    assert admin_service.ledger(db, user=audit, filters={'keyword': other.request_no})['total'] == 1
    assert admin_service.ledger(db, user=audit, filters={'status': 'archived'})['total'] == 0
    assert admin_service.ledger(db, user=audit, filters={'overdue': True})['total'] == 0
    assert admin_service.ledger(db, user=audit, filters={}, page=2, page_size=500)['page_size'] == admin_service.MAX_PAGE_SIZE


def test_ledger_total_excludes_voided(db):
    audit = person(db, ROLES['audit'])
    keep, drop = new_request(db), new_request(db)
    admin_service.void_request(db, request_id=drop.id, user=person(db, 4), reason='走错了')
    assert admin_service.ledger(db, user=audit, filters={})['total_amount'] == str(service.effective_amount(keep))


def test_csv_neutralizes_formula_cells_and_logs_the_export(db):
    audit = person(db, ROLES['audit'])
    request = new_request(db)
    request.material_name = '=HYPERLINK("http://evil")'
    db.flush()
    content = admin_service.ledger_csv(db, user=audit, filters={})
    assert content.startswith('﻿')
    rows = list(csv.DictReader(io.StringIO(content.lstrip('﻿'))))
    assert rows[0]['物料'].startswith("'=")
    assert rows[0]['单号'] == request.request_no
    assert db.query(AuditLog).filter(AuditLog.action == 'procurement_ledger_export').count() == 1


@pytest.mark.parametrize('value', ['=1+1', '+1', '-1', '@x', '\tx'])
def test_csv_cell_escapes(value):
    assert admin_service._csv_cell(value).startswith("'")


def test_blacklisted_supplier_cannot_quote_even_with_spacing_or_case(db):
    db.add(ProcurementSupplier(name='Bad Co', normalized_name=service.normalize_supplier('Bad Co'), status=flow.SUPPLIER_BLACKLISTED))
    db.flush()
    request = new_request(db, quantity='1', price='100')
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError, match='黑名单'):
        quote(db, request, ' bad  co ')
    assert request.current_step == 'quotation'


def test_blacklisted_supplier_cannot_get_exemption(db):
    db.add(ProcurementSupplier(name='坏公司', normalized_name=service.normalize_supplier('坏公司'), status=flow.SUPPLIER_BLACKLISTED))
    db.flush()
    request = new_request(db)
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError, match='黑名单'):
        act(db, request, ROLES['purchasing'], 'request_exemption', reason='独家供应', supplier='坏公司', unit_price='100')


def test_new_supplier_is_registered_as_pending_once(db):
    first = new_request(db, quantity='1', price='100')
    to_quotation(db, first)
    quote(db, first, '新公司')
    second = new_request(db, quantity='1', price='100')
    to_quotation(db, second)
    quote(db, second, ' 新公司 ')
    rows = db.query(ProcurementSupplier).all()
    assert [(row.name, row.status) for row in rows] == [('新公司', flow.SUPPLIER_PENDING)]
    stats = admin_service.list_suppliers(db, user=person(db, ROLES['audit']))
    assert stats[0]['quote_count'] == 2
    assert stats[0]['win_count'] == 2
    assert stats[0]['total_amount'] == '200.00'


def test_only_purchasing_lead_and_admin_edit_suppliers(db):
    with pytest.raises(service.ProcurementError):
        admin_service.save_supplier(db, user=person(db, ROLES['purchasing']), data={'name': '甲'})
    with pytest.raises(service.ProcurementError):
        admin_service.save_supplier(db, user=person(db, ROLES['general_manager']), data={'name': '甲'})
    supplier = admin_service.save_supplier(db, user=person(db, ROLES['purchasing_lead']), data={'name': '甲', 'status': 'qualified'})
    assert supplier.status == 'qualified'
    updated = admin_service.save_supplier(db, user=person(db, 4), data={'name': '甲', 'status': 'blacklisted', 'remark': '以次充好'}, supplier_id=supplier.id)
    assert updated.status == 'blacklisted'
    assert db.query(AuditLog).filter(AuditLog.action == 'procurement_supplier_save').count() == 2
    with pytest.raises(service.ProcurementError):
        admin_service.save_supplier(db, user=person(db, 4), data={'name': '甲'})
    with pytest.raises(service.ProcurementError):
        admin_service.save_supplier(db, user=person(db, 4), data={'name': '甲', 'status': 'vip'}, supplier_id=supplier.id)


def test_void_rules(db):
    request = new_request(db)
    with pytest.raises(service.ProcurementError, match='理由'):
        admin_service.void_request(db, request_id=request.id, user=person(db, 4), reason='  ')
    with pytest.raises(service.ProcurementError):
        admin_service.void_request(db, request_id=request.id, user=person(db, ROLES['purchasing']), reason='错')
    admin_service.void_request(db, request_id=request.id, user=person(db, ROLES['purchasing_lead']), reason='重复提报')
    assert request.status == flow.STATUS_CANCELLED
    with pytest.raises(service.ProcurementError):
        admin_service.void_request(db, request_id=request.id, user=person(db, 4), reason='再来')
    late = new_request(db)
    late.current_step = 'payment_booking'
    db.flush()
    with pytest.raises(service.ProcurementError, match='付款'):
        admin_service.void_request(db, request_id=late.id, user=person(db, 4), reason='错')


def test_admin_can_prepare_while_module_is_off_but_cannot_run_requests(db, client, monkeypatch):
    monkeypatch.setattr('app.config.settings.PROCUREMENT_ENABLED', False)
    as_user(db, 4)
    meta = client.get('/api/v1/procurement/meta').json()
    assert meta['enabled'] is False
    assert meta['can_manage'] is True
    assert client.get('/api/v1/procurement/assignments').status_code == 200
    assert client.get('/api/v1/procurement/suppliers').status_code == 200
    assert client.get('/api/v1/procurement/ledger').status_code == 200
    assert client.post('/api/v1/procurement/requests', json={}).status_code == 404
    as_user(db, ROLES['audit'])
    assert client.get('/api/v1/procurement/ledger').status_code == 404


def test_board_extras_report_amounts_and_step_hours(db, client):
    request = new_request(db, quantity='1', price='100')
    to_quotation(db, request)
    quote(db, request, '甲')
    db.commit()
    as_user(db, ROLES['audit'])
    board = client.get('/api/v1/procurement/board').json()
    assert board['month_by_category'] == [{'category': '备品备件', 'amount': '100.00'}]
    assert board['top_suppliers'] == [{'supplier': '甲', 'amount': '100.00'}]
    assert board['emergency_backfill_overdue'] == 0
    assert {row['step'] for row in board['step_hours']} >= {'workshop_approval', 'stock_review'}


def test_spacing_variant_of_a_supplier_counts_as_one_quote(db):
    request = new_request(db, quantity='100', price='100')
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError, match='只算一家'):
        quote(db, request, '甲公司', '甲 公司')


def test_supplier_blacklisted_after_selection_cannot_get_a_contract(db):
    request = new_request(db, quantity='1', price='100')
    to_quotation(db, request)
    quote(db, request, '后来出事公司')
    act(db, request, ROLES['division_lead'], 'approve')
    supplier = db.query(ProcurementSupplier).one()
    supplier.status = flow.SUPPLIER_BLACKLISTED
    db.flush()
    with pytest.raises(service.ProcurementError, match='黑名单'):
        act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='order', contract_no='D1', amount='100')
    assert request.current_step == 'contract_draft'


def test_too_long_supplier_name_is_rejected_not_a_server_error(db):
    request = new_request(db, quantity='1', price='100')
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError, match='不能超过'):
        quote(db, request, '长' * 129)
    with pytest.raises(service.ProcurementError, match='不能超过'):
        admin_service.save_supplier(db, user=person(db, 4), data={'name': '长' * 129})


def test_stock_closed_requests_do_not_count_as_spend(db, client):
    closed = new_request(db)
    closed.status = flow.STATUS_CLOSED_STOCK
    db.commit()
    audit = person(db, ROLES['audit'])
    assert admin_service.ledger(db, user=audit, filters={})['total_amount'] == '0'
    assert admin_service.board_extras(db)['month_by_category'] == []


def test_assignment_change_is_audited(db, client):
    as_user(db, 4)
    assert client.post('/api/v1/procurement/assignments', json={'user_id': 1, 'role': 'gate'}).status_code == 200
    log = db.query(AuditLog).filter(AuditLog.action == 'procurement_assignment').one()
    assert log.new_value == {'role': 'gate', 'enabled': True}

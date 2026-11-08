from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.deps import get_current_user, get_db
from app.database import Base
from app.domain import procurement_flow as flow
from app.main import app
from app.models.master import Workshop
from app.models.procurement import (
    ProcurementAssignment,
    ProcurementDocument,
    ProcurementQuote,
    ProcurementRequest,
    ProcurementStepLog,
)
from app.models.system import User
from app.services import procurement_service as service

SHANGHAI = ZoneInfo('Asia/Shanghai')
TABLES = [
    Workshop.__table__, User.__table__, ProcurementAssignment.__table__, ProcurementRequest.__table__,
    ProcurementQuote.__table__, ProcurementDocument.__table__, ProcurementStepLog.__table__,
]
ROLES = {
    flow.ROLE_EQUIPMENT: 11, flow.ROLE_WAREHOUSE: 12, flow.ROLE_PURCHASING: 13, flow.ROLE_PURCHASING_LEAD: 14,
    flow.ROLE_DIVISION_LEAD: 15, flow.ROLE_GENERAL_MANAGER: 16, flow.ROLE_LEGAL: 17, flow.ROLE_FINANCE: 18,
    flow.ROLE_ACCOUNTANT: 19, flow.ROLE_GATE: 20, flow.ROLE_QUALITY: 21, flow.ROLE_AUDIT: 22,
}


@pytest.fixture()
def db(tmp_path, monkeypatch) -> Iterator[Session]:
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'PROCUREMENT_ENABLED', True)
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    session.add(Workshop(id=1, code='RZ', name='热轧', is_active=True))
    session.add(Workshop(id=2, code='LJ', name='拉矫', is_active=True))
    session.add(User(id=1, username='stat', password_hash='x', name='统计员', role='consumable_stat', workshop_id=1))
    session.add(User(id=2, username='dir', password_hash='x', name='车间主任', role='workshop_director', workshop_id=1))
    session.add(User(id=3, username='dir2', password_hash='x', name='别的主任', role='workshop_director', workshop_id=2))
    session.add(User(id=4, username='admin', password_hash='x', name='管理员', role='admin'))
    for role, user_id in ROLES.items():
        session.add(User(id=user_id, username=role, password_hash='x', name=role, role='operator'))
        session.add(ProcurementAssignment(user_id=user_id, role=role))
    session.commit()
    yield session
    session.close()


def person(db: Session, user_id: int) -> User:
    return db.get(User, user_id)


def new_request(db: Session, *, quantity='20', price='100', category='备品备件', emergency=False) -> ProcurementRequest:
    return service.create_request(db, user=person(db, 1), data={
        'material_name': '6205轴承', 'specification': '6205', 'unit': '个', 'category': category,
        'quantity': quantity, 'estimated_unit_price': price, 'purpose': '热轧检修', 'is_emergency': emergency,
    })


def act(db: Session, request: ProcurementRequest, user_id: int, action: str, comment=None, **payload) -> ProcurementRequest:
    return service.apply_action(
        db, request_id=request.id, user=person(db, user_id), action=action,
        expected_step=request.current_step, comment=comment, payload=payload,
    )


def upload(db: Session, request: ProcurementRequest, user_id: int, doc_type: str) -> None:
    service.save_document(db, request_id=request.id, user=person(db, user_id), doc_type=doc_type, file_name='a.pdf', content=b'%PDF-1.4 x', content_type='application/pdf')


def to_quotation(db, request):
    act(db, request, 1, 'submit')
    act(db, request, 2, 'approve')
    if request.current_step == 'tech_review':
        act(db, request, ROLES['equipment'], 'approve')
    act(db, request, ROLES['warehouse'], 'confirm_stock', stock_quantity='0')
    assert request.current_step == 'quotation'


def quotes(*prices):
    return [{'supplier': f'供应商{i}', 'unit_price': str(p)} for i, p in enumerate(prices)]


def test_quote_and_approval_thresholds_follow_the_policy():
    assert flow.required_quote_count(Decimal('4999.99')) == 1
    assert flow.required_quote_count(Decimal('5000')) == 2
    assert flow.required_quote_count(Decimal('49999.99')) == 2
    assert flow.required_quote_count(Decimal('50000')) == 3
    assert flow.purchase_approver_role(Decimal('4999.99')) == flow.ROLE_DIVISION_LEAD
    assert flow.purchase_approver_role(Decimal('5000')) == flow.ROLE_GENERAL_MANAGER
    assert flow.can_use_order(Decimal('4999.99')) is True
    assert flow.can_use_order(Decimal('5000')) is False


def test_steps_cover_all_sixteen_numbers_in_order():
    assert sorted({step.number for step in flow.STEPS}) == list(range(1, 17))
    assert len(flow.DOCUMENT_TYPES) == 9


def test_small_order_runs_all_the_way_and_skips_legal_and_tech(db):
    request = new_request(db, quantity='20', price='100')
    to_quotation(db, request)
    act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=quotes(100), selected_index=0)
    assert request.current_step == 'purchase_approval'
    assert service.step_role(request) == flow.ROLE_DIVISION_LEAD
    act(db, request, ROLES['division_lead'], 'approve')
    act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='order', amount='2000', contract_no='DD-1')
    assert request.current_step == 'finance_contract_review'
    act(db, request, ROLES['finance'], 'approve', signing_entity='河南鑫泰')
    act(db, request, ROLES['purchasing'], 'sign')
    act(db, request, ROLES['gate'], 'register', supplier='供应商0', goods='轴承', quantity='20', plate_no='豫A1')
    act(db, request, ROLES['warehouse'], 'accept', accepted_quantity='20')
    assert request.current_step == 'document_collection'
    upload(db, request, ROLES['purchasing'], 'delivery_note')
    upload(db, request, ROLES['purchasing'], 'invoice')
    act(db, request, ROLES['purchasing'], 'submit_payment', invoice_no='F1', invoice_amount='2000', payment_amount='2000')
    act(db, request, ROLES['finance'], 'approve')
    act(db, request, ROLES['general_manager'], 'approve')
    act(db, request, ROLES['accountant'], 'book', voucher_no='记-1')
    assert request.status == flow.STATUS_ARCHIVED
    assert request.paid_amount == Decimal('2000')
    steps = [row.step for row in db.query(ProcurementStepLog).filter_by(request_id=request.id, action='approve').all()]
    assert 'legal_review' not in steps and 'tech_review' not in steps


def test_equipment_goes_through_tech_review_and_other_categories_do_not(db):
    request = new_request(db, category='设备配件')
    act(db, request, 1, 'submit')
    act(db, request, 2, 'approve')
    assert request.current_step == 'tech_review'
    other = new_request(db, category='劳保用品')
    act(db, other, 1, 'submit')
    act(db, other, 2, 'approve')
    assert other.current_step == 'stock_review'


def test_stock_sufficient_closes_request_and_partial_buys_the_difference(db):
    enough = new_request(db)
    act(db, enough, 1, 'submit')
    act(db, enough, 2, 'approve')
    act(db, enough, ROLES['warehouse'], 'confirm_stock', stock_quantity='30', available_quantity='20')
    assert enough.status == flow.STATUS_CLOSED_STOCK

    partial = new_request(db)
    act(db, partial, 1, 'submit')
    act(db, partial, 2, 'approve')
    act(db, partial, ROLES['warehouse'], 'confirm_stock', stock_quantity='5', available_quantity='5')
    assert partial.current_step == 'quotation'
    assert partial.purchase_quantity == Decimal('15')


def test_too_few_quotes_cannot_be_submitted(db):
    request = new_request(db, quantity='100', price='100')
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError) as error:
        act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=quotes(100), selected_index=0)
    assert error.value.extra == {'required': 2, 'actual': 1}
    act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=quotes(100, 110), selected_index=0)
    assert request.current_step == 'quotation_confirm'
    act(db, request, ROLES['purchasing_lead'], 'approve')
    assert service.step_role(request) == flow.ROLE_GENERAL_MANAGER


def test_low_selected_price_cannot_dodge_the_three_quote_rule(db):
    request = new_request(db, quantity='100', price='500')
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError) as error:
        act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=quotes(400, 600), selected_index=0)
    assert error.value.extra['required'] == 3


def test_duplicate_supplier_counts_once(db):
    request = new_request(db, quantity='100', price='100')
    to_quotation(db, request)
    same = [{'supplier': '甲', 'unit_price': '100'}, {'supplier': '甲', 'unit_price': '101'}]
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=same, selected_index=0)


def test_exemption_needs_division_lead_then_goes_to_amount_approver(db):
    request = new_request(db, quantity='100', price='100')
    to_quotation(db, request)
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'request_exemption', reason='图省事', supplier='甲', unit_price='100')
    act(db, request, ROLES['purchasing'], 'request_exemption', reason='独家供应', supplier='甲', unit_price='100')
    assert request.current_step == 'exemption_approval'
    act(db, request, ROLES['division_lead'], 'approve')
    assert request.current_step == 'purchase_approval'
    assert service.step_role(request) == flow.ROLE_GENERAL_MANAGER


def to_contract(db, request, price=100):
    to_quotation(db, request)
    amount = Decimal(request.quantity) * Decimal(str(price))
    act(db, request, ROLES['purchasing'], 'submit_quotes', quotes=quotes(*[price + i for i in range(flow.required_quote_count(amount))]), selected_index=0)
    if request.current_step == 'quotation_confirm':
        act(db, request, ROLES['purchasing_lead'], 'approve')
    approver = ROLES[service.step_role(request)]
    act(db, request, approver, 'approve')
    assert request.current_step == 'contract_draft'
    return amount


def test_large_purchase_cannot_use_order_and_contract_goes_legal_then_finance(db):
    request = new_request(db, quantity='100', price='100')
    amount = to_contract(db, request)
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='order', amount=str(amount), contract_no='D')
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='contract', amount=str(amount), contract_no='H')
    upload(db, request, ROLES['purchasing'], 'contract_draft')
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='contract', amount=str(amount + 1), contract_no='H')
    act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='contract', amount=str(amount), contract_no='H')
    assert request.current_step == 'legal_review'
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['legal'], 'reject')
    act(db, request, ROLES['legal'], 'reject', comment='缺违约责任')
    assert request.current_step == 'contract_draft'
    act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='contract', amount=str(amount), contract_no='H')
    act(db, request, ROLES['legal'], 'approve')
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['finance'], 'approve')
    act(db, request, ROLES['finance'], 'approve', signing_entity='河南鑫泰')
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'sign')
    upload(db, request, ROLES['purchasing'], 'contract')
    act(db, request, ROLES['purchasing'], 'sign')
    assert request.current_step == 'gate_registration'


def to_documents(db, request, *, needs_quality=False):
    amount = to_contract(db, request)
    act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='order', amount=str(amount), contract_no='D')
    act(db, request, ROLES['finance'], 'approve', signing_entity='河南鑫泰')
    act(db, request, ROLES['purchasing'], 'sign')
    act(db, request, ROLES['gate'], 'register', supplier='甲', goods='轴承', quantity='20', plate_no='豫A1')
    act(db, request, ROLES['warehouse'], 'accept', accepted_quantity='20', needs_quality_check=needs_quality)
    return amount


def test_payment_needs_all_documents_and_matching_amounts(db):
    request = new_request(db)
    amount = to_documents(db, request)
    with pytest.raises(service.ProcurementError) as error:
        act(db, request, ROLES['purchasing'], 'submit_payment', invoice_no='F', invoice_amount=str(amount), payment_amount=str(amount))
    assert error.value.extra['missing'] == ['delivery_note', 'invoice']
    upload(db, request, ROLES['purchasing'], 'delivery_note')
    upload(db, request, ROLES['purchasing'], 'invoice')
    with pytest.raises(service.ProcurementError) as mismatch:
        act(db, request, ROLES['purchasing'], 'submit_payment', invoice_no='F', invoice_amount=str(amount + 1), payment_amount=str(amount))
    assert '不一致' in mismatch.value.message
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['purchasing'], 'submit_payment', invoice_no='F', invoice_amount=str(amount), payment_amount=str(amount + 1))
    act(db, request, ROLES['purchasing'], 'submit_payment', invoice_no='F', invoice_amount=str(amount), payment_amount=str(amount))
    assert request.current_step == 'payment_review'
    act(db, request, ROLES['finance'], 'reject', comment='发票抬头不对')
    assert request.current_step == 'document_collection'


def test_quality_required_blocks_receipt_until_passed(db):
    request = new_request(db)
    to_documents(db, request, needs_quality=True)
    assert request.current_step == 'quality_check'
    act(db, request, ROLES['quality'], 'approve')
    assert request.current_step == 'document_collection'
    assert 'quality_record' in service.present_documents(db, request)


def test_refused_delivery_needs_signed_note_and_returns_to_gate(db):
    request = new_request(db)
    amount = to_contract(db, request)
    act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='order', amount=str(amount), contract_no='D')
    act(db, request, ROLES['finance'], 'approve', signing_entity='河南鑫泰')
    act(db, request, ROLES['purchasing'], 'sign')
    act(db, request, ROLES['gate'], 'register', supplier='甲', goods='轴承', quantity='20', plate_no='豫A1')
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['warehouse'], 'refuse', reason='规格不符')
    upload(db, request, ROLES['warehouse'], 'rejection_note')
    act(db, request, ROLES['warehouse'], 'refuse', reason='规格不符')
    assert request.current_step == 'gate_registration'
    assert 'gate' not in request.details


def test_emergency_goes_to_gate_first_then_backfills_within_three_workdays(db):
    request = new_request(db, emergency=True)
    with pytest.raises(service.ProcurementError):
        act(db, request, 1, 'submit')
    act(db, request, 1, 'submit', emergency_report='已电话报告分管领导')
    assert request.current_step == 'gate_registration'
    act(db, request, ROLES['gate'], 'register', supplier='甲', goods='轴承', quantity='20', plate_no='豫A1')
    now = datetime(2026, 11, 6, 9, 0, tzinfo=SHANGHAI)
    service.apply_action(db, request_id=request.id, user=person(db, ROLES['warehouse']), action='accept', expected_step='acceptance', payload={'accepted_quantity': '20'}, now=now)
    assert request.current_step == 'quotation'
    assert request.backfill_due_on.isoformat() == '2026-11-11'
    act(db, request, ROLES['purchasing'], 'request_exemption', reason='生产线紧急抢修', supplier='甲', unit_price='100')
    act(db, request, ROLES['division_lead'], 'approve')
    act(db, request, ROLES['division_lead'], 'approve')
    act(db, request, ROLES['purchasing'], 'submit_contract', doc_kind='order', amount='2000', contract_no='D')
    act(db, request, ROLES['finance'], 'approve', signing_entity='河南鑫泰')
    act(db, request, ROLES['purchasing'], 'sign')
    assert request.current_step == 'document_collection'


def test_emergency_over_limit_needs_general_manager(db):
    request = new_request(db, quantity='100', price='3000', emergency=True)
    act(db, request, 1, 'submit', emergency_report='已报告')
    assert request.current_step == 'emergency_consent'
    with pytest.raises(service.ProcurementError):
        act(db, request, ROLES['division_lead'], 'approve')
    act(db, request, ROLES['general_manager'], 'approve')
    assert request.current_step == 'gate_registration'


def test_only_the_step_owner_can_act_and_admin_cannot_approve(db):
    request = new_request(db)
    act(db, request, 1, 'submit')
    for user_id in (3, 4, ROLES['general_manager'], 1):
        with pytest.raises(service.ProcurementError) as error:
            act(db, request, user_id, 'approve')
        assert error.value.status_code == 403


def test_stale_step_is_refused(db):
    request = new_request(db)
    act(db, request, 1, 'submit')
    with pytest.raises(service.ProcurementError) as error:
        service.apply_action(db, request_id=request.id, user=person(db, 1), action='submit', expected_step='draft')
    assert error.value.status_code == 409


def test_every_action_is_logged(db):
    request = new_request(db)
    act(db, request, 1, 'submit')
    act(db, request, 2, 'reject', comment='用量不对')
    logs = db.query(ProcurementStepLog).filter_by(request_id=request.id).order_by(ProcurementStepLog.id).all()
    assert [(row.action, row.to_step, row.actor_name) for row in logs] == [
        ('create', 'draft', '统计员'), ('submit', 'workshop_approval', '统计员'), ('reject', 'draft', '车间主任'),
    ]
    assert logs[-1].comment == '用量不对'


def test_stock_review_deadline_is_same_day_and_payment_review_five_workdays():
    entered = datetime(2026, 11, 6, 9, 0, tzinfo=SHANGHAI)
    assert flow.step_deadline(flow.STEP_BY_CODE['stock_review'], entered).date().isoformat() == '2026-11-06'
    assert flow.step_deadline(flow.STEP_BY_CODE['payment_review'], entered).date().isoformat() == '2026-11-13'
    assert flow.step_deadline(flow.STEP_BY_CODE['quality_check'], entered).isoformat().startswith('2026-11-07T09:00')
    assert flow.step_deadline(flow.STEP_BY_CODE['quotation'], entered) is None


def test_split_orders_are_flagged_not_blocked():
    base = datetime(2026, 11, 1, tzinfo=SHANGHAI)
    rows = [
        {'material_name': '轴承', 'supplier': '甲', 'amount': Decimal('3000'), 'created_at': base, 'request_no': 'A'},
        {'material_name': '轴承', 'supplier': '甲', 'amount': Decimal('2500'), 'created_at': base.replace(day=5), 'request_no': 'B'},
        {'material_name': '轴承', 'supplier': '乙', 'amount': Decimal('2500'), 'created_at': base, 'request_no': 'C'},
    ]
    warnings = flow.split_order_warnings(rows)
    assert len(warnings) == 1
    assert warnings[0]['request_nos'] == ['A', 'B']


def test_upload_rejects_wrong_type_and_only_current_owner_can_upload(db):
    request = new_request(db)
    with pytest.raises(service.ProcurementError):
        service.save_document(db, request_id=request.id, user=person(db, 1), doc_type='quote', file_name='a.exe', content=b'x')
    with pytest.raises(service.ProcurementError) as error:
        service.save_document(db, request_id=request.id, user=person(db, ROLES['warehouse']), doc_type='quote', file_name='a.pdf', content=b'x')
    assert error.value.status_code == 403


@pytest.fixture()
def client(db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_user(db, user_id):
    app.dependency_overrides[get_current_user] = lambda: person(db, user_id)


def test_api_is_hidden_until_enabled(db, client, monkeypatch):
    as_user(db, 1)
    monkeypatch.setattr(settings, 'PROCUREMENT_ENABLED', False)
    assert client.get('/api/v1/procurement/meta').status_code == 404


def test_api_runs_request_and_guards_views(db, client):
    as_user(db, 1)
    body = {'material_name': '轴承', 'unit': '个', 'category': '备品备件', 'quantity': '2', 'estimated_unit_price': '10', 'purpose': '检修'}
    created = client.post('/api/v1/procurement/requests', json=body)
    assert created.status_code == 200, created.text
    request_id = created.json()['id']
    assert created.json()['request_no'].startswith('CG')

    result = client.post(f'/api/v1/procurement/requests/{request_id}/actions', json={'action': 'submit', 'expected_step': 'draft'})
    assert result.json()['current_step'] == 'workshop_approval'
    assert client.get('/api/v1/procurement/board').status_code == 403
    assert client.get('/api/v1/procurement/requests?scope=all').status_code == 403

    as_user(db, 3)
    assert client.get(f'/api/v1/procurement/requests/{request_id}').status_code == 403
    assert client.get('/api/v1/procurement/requests').json() == []

    as_user(db, 2)
    todo = client.get('/api/v1/procurement/requests').json()
    assert [item['id'] for item in todo] == [request_id]
    assert todo[0]['can_act'] is True

    as_user(db, ROLES['audit'])
    board = client.get('/api/v1/procurement/board').json()
    assert board['open_count'] == 1
    assert [row['number'] for row in board['funnel']] == list(range(1, 17))
    assert client.post('/api/v1/procurement/assignments', json={'user_id': 1, 'role': 'gate'}).status_code == 403


def test_api_uploads_and_downloads_a_document(db, client):
    as_user(db, 1)
    body = {'material_name': '轴承', 'unit': '个', 'category': '备品备件', 'quantity': '2', 'estimated_unit_price': '10', 'purpose': '检修'}
    request_id = client.post('/api/v1/procurement/requests', json=body).json()['id']
    uploaded = client.post(f'/api/v1/procurement/requests/{request_id}/documents', data={'doc_type': 'quote'}, files={'file': ('报价.pdf', b'%PDF-1.4', 'application/pdf')})
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()['id']
    assert client.get(f'/api/v1/procurement/documents/{document_id}/file').content == b'%PDF-1.4'
    as_user(db, 3)
    assert client.get(f'/api/v1/procurement/documents/{document_id}/file').status_code == 403

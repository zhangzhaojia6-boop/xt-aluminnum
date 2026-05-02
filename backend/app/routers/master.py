from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import get_current_manager_user
from app.core.workshop_templates import normalize_workshop_type
from app.models.master import Employee, Equipment, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User
from app.schemas.common import PaginatedResponse
from app.schemas.master import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    EquipmentAccountSummaryOut,
    EquipmentCreateWithAccountRequest,
    EquipmentCreateWithAccountResponse,
    EquipmentOut,
    EquipmentPinResetResponse,
    EquipmentStatusToggleRequest,
    EquipmentUpdate,
    MasterCodeAliasCreate,
    MasterCodeAliasOut,
    MasterCodeAliasUpdate,
    ShiftConfigCreate,
    ShiftConfigOut,
    ShiftConfigUpdate,
    TeamCreate,
    TeamOut,
    TeamUpdate,
    WorkshopCreate,
    WorkshopOut,
    WorkshopUpdate,
)
from app.schemas.templates import WorkshopTemplateConfigOut, WorkshopTemplateConfigUpsert
from app.services import equipment_service, master_service, workshop_template_service
from app.services.audit_service import log_action
from app.services.yield_rate_deprecation_map_service import build_yield_rate_deprecation_map


router = APIRouter(tags=['master'])


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{entity}不存在')


def _require_admin(current_user: User) -> None:
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅管理员可操作')


def _paginate_query(query, *, skip: int, limit: int) -> dict:
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {'items': items, 'total': total, 'skip': skip, 'limit': limit}


def _paginate_items(items: list, *, skip: int, limit: int) -> dict:
    total = len(items)
    return {'items': items[skip : skip + limit], 'total': total, 'skip': skip, 'limit': limit}


@router.get('/yield-rate-deprecation-map')
def get_yield_rate_deprecation_map(
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    _ = current_user
    return build_yield_rate_deprecation_map()


@router.get('/workshops', response_model=PaginatedResponse[WorkshopOut])
def list_workshops(
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    query = db.query(Workshop).filter(Workshop.is_active.is_(True)).order_by(Workshop.sort_order.asc(), Workshop.id.asc())
    return _paginate_query(query, skip=skip, limit=limit)


@router.post('/workshops', response_model=WorkshopOut, status_code=status.HTTP_201_CREATED)
def create_workshop(
    request: Request,
    payload: WorkshopCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Workshop:
    data = payload.model_dump()
    data['workshop_type'] = normalize_workshop_type(data.get('workshop_type'))
    item = Workshop(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.name,
        action='create',
        module='master',
        table_name='workshops',
        record_id=item.id,
        new_value={'code': item.code, 'name': item.name},
        ip_address=request.client.host if request.client else None,
    )
    return item


@router.put('/workshops/{workshop_id}', response_model=WorkshopOut)
def update_workshop(
    workshop_id: int,
    payload: WorkshopUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Workshop:
    _ = current_user
    item = db.get(Workshop, workshop_id)
    if not item:
        raise _not_found('车间')
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == 'workshop_type':
            value = normalize_workshop_type(value)
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete('/workshops/{workshop_id}')
def delete_workshop(
    workshop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    item = db.get(Workshop, workshop_id)
    if not item:
        raise _not_found('车间')
    item.is_active = False
    db.commit()
    return {'success': True, 'data': None, 'message': '删除成功', 'total': None}


@router.get('/aliases', response_model=PaginatedResponse[MasterCodeAliasOut])
def list_aliases(
    entity_type: str | None = None,
    source_type: str | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    items = master_service.list_aliases(
        db,
        entity_type=entity_type,
        source_type=source_type,
        is_active=is_active,
    )
    payload = [MasterCodeAliasOut.model_validate(item) for item in items]
    return _paginate_items(payload, skip=skip, limit=limit)


@router.post('/aliases', response_model=MasterCodeAliasOut, status_code=status.HTTP_201_CREATED)
def create_alias(
    payload: MasterCodeAliasCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MasterCodeAliasOut:
    item = master_service.create_alias(db, payload=payload.model_dump(), operator=current_user)
    return MasterCodeAliasOut.model_validate(item)


@router.put('/aliases/{alias_id}', response_model=MasterCodeAliasOut)
def update_alias(
    alias_id: int,
    payload: MasterCodeAliasUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MasterCodeAliasOut:
    try:
        item = master_service.update_alias(
            db,
            alias_id=alias_id,
            payload=payload.model_dump(exclude_unset=True),
            operator=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MasterCodeAliasOut.model_validate(item)


@router.delete('/aliases/{alias_id}')
def delete_alias(
    alias_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        master_service.delete_alias(db, alias_id=alias_id, operator=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {'success': True, 'data': None, 'message': '删除成功', 'total': None}


@router.get('/workshop-templates/{template_key}', response_model=WorkshopTemplateConfigOut, name='workshop-template-detail')
def get_workshop_template_detail(
    template_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopTemplateConfigOut:
    _require_admin(current_user)
    payload = workshop_template_service.get_workshop_template_definition(template_key, db=db)
    return WorkshopTemplateConfigOut(**payload)


@router.put('/workshop-templates/{template_key}', response_model=WorkshopTemplateConfigOut, name='workshop-template-upsert')
def upsert_workshop_template(
    template_key: str,
    payload: WorkshopTemplateConfigUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopTemplateConfigOut:
    _require_admin(current_user)
    workshop_template_service.upsert_workshop_template_config(
        db,
        template_key=template_key,
        payload=payload.model_dump(),
    )
    result = workshop_template_service.get_workshop_template_definition(template_key, db=db)
    return WorkshopTemplateConfigOut(**result)


@router.get('/teams', response_model=PaginatedResponse[TeamOut])
def list_teams(
    workshop_id: int | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    query = db.query(Team).filter(Team.is_active.is_(True)).order_by(Team.sort_order.asc(), Team.id.asc())
    if workshop_id:
        query = query.filter(Team.workshop_id == workshop_id)
    return _paginate_query(query, skip=skip, limit=limit)


@router.post('/teams', response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    request: Request,
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Team:
    if not db.get(Workshop, payload.workshop_id):
        raise HTTPException(status_code=400, detail='关联车间不存在')
    item = Team(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.name,
        action='create',
        module='master',
        table_name='teams',
        record_id=item.id,
        new_value={'code': item.code, 'name': item.name},
        ip_address=request.client.host if request.client else None,
    )
    return item


@router.put('/teams/{team_id}', response_model=TeamOut)
def update_team(
    team_id: int,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Team:
    _ = current_user
    item = db.get(Team, team_id)
    if not item:
        raise _not_found('班组')
    data = payload.model_dump(exclude_unset=True)
    if 'workshop_id' in data and data['workshop_id'] is not None and not db.get(Workshop, data['workshop_id']):
        raise HTTPException(status_code=400, detail='关联车间不存在')
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete('/teams/{team_id}')
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    item = db.get(Team, team_id)
    if not item:
        raise _not_found('班组')
    item.is_active = False
    db.commit()
    return {'success': True, 'data': None, 'message': '删除成功', 'total': None}


@router.get('/employees', response_model=PaginatedResponse[EmployeeOut])
def list_employees(
    workshop_id: int | None = None,
    team_id: int | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    query = db.query(Employee).filter(Employee.is_active.is_(True)).order_by(Employee.id.asc())
    if workshop_id:
        query = query.filter(Employee.workshop_id == workshop_id)
    if team_id:
        query = query.filter(Employee.team_id == team_id)
    return _paginate_query(query, skip=skip, limit=limit)


@router.post('/employees', response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    request: Request,
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Employee:
    if not db.get(Workshop, payload.workshop_id):
        raise HTTPException(status_code=400, detail='关联车间不存在')
    if payload.team_id and not db.get(Team, payload.team_id):
        raise HTTPException(status_code=400, detail='关联班组不存在')
    item = Employee(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.name,
        action='create',
        module='master',
        table_name='employees',
        record_id=item.id,
        new_value={'employee_no': item.employee_no, 'name': item.name},
        ip_address=request.client.host if request.client else None,
    )
    return item


@router.put('/employees/{employee_id}', response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Employee:
    _ = current_user
    item = db.get(Employee, employee_id)
    if not item:
        raise _not_found('员工')
    data = payload.model_dump(exclude_unset=True)
    if 'workshop_id' in data and data['workshop_id'] is not None and not db.get(Workshop, data['workshop_id']):
        raise HTTPException(status_code=400, detail='关联车间不存在')
    if 'team_id' in data and data['team_id'] is not None and not db.get(Team, data['team_id']):
        raise HTTPException(status_code=400, detail='关联班组不存在')
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete('/employees/{employee_id}')
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    item = db.get(Employee, employee_id)
    if not item:
        raise _not_found('员工')
    item.is_active = False
    db.commit()
    return {'success': True, 'data': None, 'message': '删除成功', 'total': None}


@router.get('/equipment', response_model=PaginatedResponse[EquipmentOut])
def list_equipment(
    workshop_id: int | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    query = db.query(Equipment).filter(Equipment.is_active.is_(True)).order_by(Equipment.sort_order.asc(), Equipment.id.asc())
    if workshop_id:
        query = query.filter(Equipment.workshop_id == workshop_id)
    return _paginate_query(query, skip=skip, limit=limit)


@router.get('/equipment/{equipment_id}', response_model=EquipmentOut, name='equipment-detail')
def get_equipment_detail(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Equipment:
    _ = current_user
    item = db.get(Equipment, equipment_id)
    if not item or not item.is_active:
        raise _not_found('机台')
    return item


@router.patch('/equipment/{equipment_id}', response_model=EquipmentOut, name='equipment-update')
def update_equipment(
    equipment_id: int,
    payload: EquipmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Equipment:
    _require_admin(current_user)
    return equipment_service.update_machine(
        db,
        equipment_id=equipment_id,
        payload=payload.model_dump(exclude_unset=True),
        operator=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )


@router.post(
    '/equipment/create-with-account',
    response_model=EquipmentCreateWithAccountResponse,
    status_code=status.HTTP_201_CREATED,
    name='equipment-create-with-account',
)
def create_equipment_with_account(
    body: EquipmentCreateWithAccountRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    summary = equipment_service.create_machine_with_account(
        db,
        workshop_id=body.workshop_id,
        code=body.code,
        name=body.name,
        machine_type=body.machine_type,
        shift_mode=body.shift_mode,
        assigned_shift_ids=body.assigned_shift_ids,
        custom_fields=body.custom_fields,
        operational_status=body.operational_status,
        operator=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )
    equipment = db.get(Equipment, summary['equipment_id'])
    return {
        'equipment': EquipmentOut.model_validate(equipment).model_dump(),
        'account': EquipmentAccountSummaryOut(
            username=summary['username'],
            pin=summary['pin'],
            qr_code=summary['qr_code'],
        ).model_dump(),
        'message': '机台创建成功，请保存账号密码',
    }


@router.post('/equipment/{equipment_id}/reset-pin', response_model=EquipmentPinResetResponse, name='equipment-reset-pin')
def reset_equipment_pin(
    equipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    return equipment_service.reset_machine_pin(
        db,
        equipment_id=equipment_id,
        operator=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )


@router.post('/equipment/{equipment_id}/toggle-status', response_model=dict, name='equipment-toggle-status')
def toggle_equipment_status(
    equipment_id: int,
    body: EquipmentStatusToggleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    return equipment_service.toggle_machine_status(
        db,
        equipment_id=equipment_id,
        operational_status=body.operational_status,
        operator=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )


@router.get('/shift-configs', response_model=PaginatedResponse[ShiftConfigOut])
def list_shift_configs(
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    return _list_shift_config_page(db, skip=skip, limit=limit)


def _list_shift_config_page(db: Session, *, skip: int, limit: int) -> dict:
    query = db.query(ShiftConfig).order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc())
    return _paginate_query(query, skip=skip, limit=limit)


@router.get('/shifts', response_model=PaginatedResponse[ShiftConfigOut])
def list_shifts_compat(
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    return _list_shift_config_page(db, skip=skip, limit=limit)


@router.post('/shift-configs', response_model=ShiftConfigOut, status_code=status.HTTP_201_CREATED)
def create_shift_config(
    request: Request,
    payload: ShiftConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShiftConfig:
    item = ShiftConfig(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.name,
        action='create',
        module='master',
        table_name='shift_configs',
        record_id=item.id,
        new_value={'code': item.code, 'name': item.name},
        ip_address=request.client.host if request.client else None,
    )
    return item


@router.put('/shift-configs/{shift_config_id}', response_model=ShiftConfigOut)
def update_shift_config(
    shift_config_id: int,
    payload: ShiftConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShiftConfig:
    _ = current_user
    item = db.get(ShiftConfig, shift_config_id)
    if not item:
        raise _not_found('班次')
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete('/shift-configs/{shift_config_id}')
def delete_shift_config(
    shift_config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    item = db.get(ShiftConfig, shift_config_id)
    if not item:
        raise _not_found('班次')
    item.is_active = False
    db.commit()
    return {'success': True, 'data': None, 'message': '删除成功', 'total': None}

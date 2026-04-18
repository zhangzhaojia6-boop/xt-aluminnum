from datetime import date, time
from typing import Any, Optional
from pydantic import BaseModel


class WorkshopBase(BaseModel):
    code: str
    name: str
    workshop_type: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class WorkshopCreate(WorkshopBase):
    pass


class WorkshopUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    workshop_type: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class WorkshopOut(WorkshopBase):
    id: int

    model_config = {"from_attributes": True}


class TeamBase(BaseModel):
    workshop_id: int
    code: str
    name: str
    sort_order: int = 0
    is_active: bool = True


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    workshop_id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class TeamOut(TeamBase):
    id: int

    model_config = {"from_attributes": True}


class EmployeeBase(BaseModel):
    employee_no: str
    name: str
    workshop_id: int
    team_id: Optional[int] = None
    position_id: Optional[int] = None
    phone: Optional[str] = None
    dingtalk_user_id: Optional[str] = None
    hire_date: Optional[date] = None
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    employee_no: Optional[str] = None
    name: Optional[str] = None
    workshop_id: Optional[int] = None
    team_id: Optional[int] = None
    position_id: Optional[int] = None
    phone: Optional[str] = None
    dingtalk_user_id: Optional[str] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None


class EmployeeOut(EmployeeBase):
    id: int

    model_config = {"from_attributes": True}


class EquipmentBase(BaseModel):
    code: str
    name: str
    workshop_id: int
    equipment_type: Optional[str] = None
    spec: Optional[str] = None
    operational_status: str = 'stopped'
    shift_mode: str = 'three'
    assigned_shift_ids: Optional[list[int]] = None
    custom_fields: Optional[list[dict[str, Any]]] = None
    qr_code: Optional[str] = None
    bound_user_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True


class EquipmentOut(EquipmentBase):
    id: int
    bound_username: Optional[str] = None
    bound_user_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    equipment_type: Optional[str] = None
    spec: Optional[str] = None
    operational_status: Optional[str] = None
    shift_mode: Optional[str] = None
    assigned_shift_ids: Optional[list[int]] = None
    custom_fields: Optional[list[dict[str, Any]]] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class EquipmentCreateWithAccountRequest(BaseModel):
    workshop_id: int
    code: str
    name: str
    machine_type: str
    shift_mode: str = 'three'
    assigned_shift_ids: Optional[list[int]] = None
    custom_fields: Optional[list[dict[str, Any]]] = None
    operational_status: str = 'stopped'


class EquipmentAccountSummaryOut(BaseModel):
    username: str
    pin: str
    qr_code: str


class EquipmentCreateWithAccountResponse(BaseModel):
    equipment: EquipmentOut
    account: EquipmentAccountSummaryOut
    message: str


class EquipmentPinResetResponse(BaseModel):
    username: str
    new_pin: str


class EquipmentStatusToggleRequest(BaseModel):
    operational_status: str


class ShiftConfigBase(BaseModel):
    code: str
    name: str
    shift_type: str
    start_time: time
    end_time: time
    is_cross_day: bool = False
    business_day_offset: int = 0
    late_tolerance_minutes: int = 30
    early_tolerance_minutes: int = 30
    workshop_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True


class ShiftConfigCreate(ShiftConfigBase):
    pass


class ShiftConfigUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    shift_type: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_cross_day: Optional[bool] = None
    business_day_offset: Optional[int] = None
    late_tolerance_minutes: Optional[int] = None
    early_tolerance_minutes: Optional[int] = None
    workshop_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ShiftConfigOut(ShiftConfigBase):
    id: int

    model_config = {"from_attributes": True}


class MasterCodeAliasBase(BaseModel):
    entity_type: str
    canonical_code: str
    alias_code: Optional[str] = None
    alias_name: Optional[str] = None
    source_type: Optional[str] = None
    is_active: bool = True


class MasterCodeAliasCreate(MasterCodeAliasBase):
    pass


class MasterCodeAliasUpdate(BaseModel):
    entity_type: Optional[str] = None
    canonical_code: Optional[str] = None
    alias_code: Optional[str] = None
    alias_name: Optional[str] = None
    source_type: Optional[str] = None
    is_active: Optional[bool] = None


class MasterCodeAliasOut(MasterCodeAliasBase):
    id: int

    model_config = {"from_attributes": True}

from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class QrLoginRequest(BaseModel):
    qr_code: str


class MachineInfo(BaseModel):
    machine_id: int
    machine_code: str
    machine_name: str
    workshop_id: int
    workshop_name: Optional[str] = None
    qr_code: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    username: str
    name: str
    role: str
    workshop_id: Optional[int] = None
    team_id: Optional[int] = None
    dingtalk_user_id: Optional[str] = None
    dingtalk_union_id: Optional[str] = None
    data_scope_type: str = 'self_team'
    assigned_shift_ids: Optional[list[int]] = None
    is_mobile_user: bool = False
    is_reviewer: bool = False
    is_manager: bool = False

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    machine_info: Optional[MachineInfo] = None


class QrLoginResponse(LoginResponse):
    machine_info: MachineInfo


class WorkshopQrResponse(BaseModel):
    type: str = 'workshop_redirect'
    workshop_code: str
    workshop_name: str


class WorkshopQuickEntryRequest(BaseModel):
    workshop_code: str
    role: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

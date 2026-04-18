from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserListItem(BaseModel):
    id: int
    username: str
    name: str
    role: str
    workshop_id: int | None = None
    workshop_name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    is_mobile_user: bool
    is_reviewer: bool
    is_manager: bool
    is_active: bool
    last_login: datetime | None = None
    bound_machine_id: int | None = None
    bound_machine_name: str | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=32)
    workshop_id: int | None = None
    team_id: int | None = None
    is_mobile_user: bool = False
    is_reviewer: bool = False
    is_manager: bool = False
    pin_code: str | None = None

    @field_validator('username', 'name', 'role')
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator('pin_code')
    @classmethod
    def validate_pin_code(cls, value: str | None) -> str | None:
        if value is None or value == '':
            return None
        if not value.isdigit() or len(value) != 6:
            raise ValueError('PIN码必须为6位数字')
        return value


class UserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    role: str | None = Field(default=None, min_length=1, max_length=32)
    workshop_id: int | None = None
    team_id: int | None = None
    is_mobile_user: bool | None = None
    is_reviewer: bool | None = None
    is_manager: bool | None = None
    is_active: bool | None = None
    pin_code: str | None = None

    @field_validator('username', 'name', 'role')
    @classmethod
    def strip_optional_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator('pin_code')
    @classmethod
    def validate_pin_code(cls, value: str | None) -> str | None:
        if value is None or value == '':
            return None
        if not value.isdigit() or len(value) != 6:
            raise ValueError('PIN码必须为6位数字')
        return value


class UserResetPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)
    pin_code: str | None = None

    @field_validator('pin_code')
    @classmethod
    def validate_pin_code(cls, value: str | None) -> str | None:
        if value is None or value == '':
            return None
        if not value.isdigit() or len(value) != 6:
            raise ValueError('PIN码必须为6位数字')
        return value


class UserResetPasswordResponse(BaseModel):
    id: int
    username: str
    message: str

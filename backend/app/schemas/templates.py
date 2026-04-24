from __future__ import annotations

from pydantic import BaseModel, Field


class WorkshopTemplateFieldBase(BaseModel):
    name: str
    label: str
    required: bool = False
    unit: str | None = None
    hint: str | None = None
    compute: str | None = None
    type: str = 'text'
    enabled: bool = True


class WorkshopTemplateFieldOut(WorkshopTemplateFieldBase):
    target: str
    section: str
    role_write: list[str] = Field(default_factory=list)
    role_read: list[str] = Field(default_factory=list)
    editable: bool = False
    readonly: bool = False


class WorkshopTemplateOut(BaseModel):
    template_key: str
    workshop_type: str
    display_name: str
    tempo: str
    supports_ocr: bool = False
    entry_fields: list[WorkshopTemplateFieldOut] = Field(default_factory=list)
    shift_fields: list[WorkshopTemplateFieldOut] = Field(default_factory=list)
    extra_fields: list[WorkshopTemplateFieldOut] = Field(default_factory=list)
    qc_fields: list[WorkshopTemplateFieldOut] = Field(default_factory=list)
    readonly_fields: list[WorkshopTemplateFieldOut] = Field(default_factory=list)


class WorkshopTemplateConfigUpsert(BaseModel):
    display_name: str
    tempo: str
    supports_ocr: bool = False
    entry_fields: list[WorkshopTemplateFieldBase] = Field(default_factory=list)
    shift_fields: list[WorkshopTemplateFieldBase] = Field(default_factory=list)
    extra_fields: list[WorkshopTemplateFieldBase] = Field(default_factory=list)
    qc_fields: list[WorkshopTemplateFieldBase] = Field(default_factory=list)
    readonly_fields: list[WorkshopTemplateFieldBase] = Field(default_factory=list)


class WorkshopTemplateConfigOut(WorkshopTemplateConfigUpsert):
    template_key: str
    workshop_type: str
    source_template_key: str
    has_override: bool = False

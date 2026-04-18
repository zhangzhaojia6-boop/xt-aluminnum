from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OCRFieldOut(BaseModel):
    value: str | None = None
    confidence: float | None = None


class OCRExtractOut(BaseModel):
    ocr_submission_id: int
    image_url: str
    raw_text: str = ''
    fields: dict[str, OCRFieldOut] = Field(default_factory=dict)


class OCRVerifyRequest(BaseModel):
    ocr_submission_id: int = Field(gt=0)
    corrected_fields: dict[str, Any] = Field(default_factory=dict)
    rejected: bool = False


class OCRVerifyOut(BaseModel):
    ocr_submission_id: int
    status: str
    prefill_payload: dict[str, Any] = Field(default_factory=dict)

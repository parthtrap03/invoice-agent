from __future__ import annotations
from datetime import datetime, date
from uuid import UUID
from typing import Optional, Any
from backend.schemas.common import BaseSchema

class InvoiceItemResponse(BaseSchema):
    id: UUID
    description: str
    quantity: int
    unit_price: float
    total_price: float

class InvoiceListResponse(BaseSchema):
    id: UUID
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    status: str
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    ai_decision: Optional[str] = None
    invoice_date: Optional[date] = None
    created_at: datetime

class InvoiceDetailResponse(BaseSchema):
    id: UUID
    invoice_number: Optional[str] = None
    vendor_id: Optional[UUID] = None
    po_id: Optional[UUID] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: Optional[str] = None
    status: str
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    ai_decision: Optional[str] = None
    ai_confidence: Optional[float] = None
    extracted_data: Optional[dict[str, Any]] = None
    validation_result: Optional[dict[str, Any]] = None
    po_match_result: Optional[dict[str, Any]] = None
    duplicate_result: Optional[dict[str, Any]] = None
    vendor_risk_result: Optional[dict[str, Any]] = None
    decision_result: Optional[dict[str, Any]] = None
    source_file_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: list[InvoiceItemResponse] = []
    vendor_name: Optional[str] = None
    po_number: Optional[str] = None

class InvoiceUploadResponse(BaseSchema):
    id: UUID
    invoice_number: Optional[str] = None
    status: str
    source_file_key: Optional[str] = None
    created_at: datetime

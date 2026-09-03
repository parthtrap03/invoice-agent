from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field

from backend.schemas.common import BaseSchema


class ExtractedLineItem(BaseSchema):
    description: str
    quantity: int = 1
    unit_price: float = 0.0
    total_price: float = 0.0


class ExtractedInvoice(BaseSchema):
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    po_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: Optional[str] = None
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    currency: str = "INR"

    extraction_method: Optional[str] = None
    raw_text: Optional[str] = None
    confidence: float = 1.0

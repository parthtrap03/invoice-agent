from __future__ import annotations
from datetime import datetime, date
from uuid import UUID
from typing import Optional
from backend.schemas.common import BaseSchema

class POItemResponse(BaseSchema):
    id: UUID
    description: str
    quantity: int
    unit_price: float
    total_price: float

class PurchaseOrderResponse(BaseSchema):
    id: UUID
    po_number: str
    vendor_id: UUID
    total_amount: float
    currency: str
    status: str
    issue_date: date
    expiry_date: Optional[date] = None
    department: str
    created_at: datetime
    items: list[POItemResponse] = []
    vendor_name: Optional[str] = None

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Optional
from backend.schemas.common import BaseSchema

class VendorResponse(BaseSchema):
    id: UUID
    vendor_code: str
    name: str
    category: str
    status: str
    contact_email: Optional[str] = None
    tax_id: Optional[str] = None
    risk_score: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from backend.schemas.common import BaseSchema

class ApprovalResponse(BaseSchema):
    id: UUID
    invoice_id: UUID
    requested_by: str
    approved_by: Optional[str] = None
    status: str
    risk_level: Optional[str] = None
    reasons: Optional[str] = None
    evidence: Optional[str] = None
    comments: Optional[str] = None
    requested_at: datetime
    decided_at: Optional[datetime] = None
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None

class ApprovalActionRequest(BaseSchema):
    comments: Optional[str] = None

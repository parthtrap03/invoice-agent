from __future__ import annotations

import uuid
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid import uuid4

from .base import Base

if TYPE_CHECKING:
    from .invoice import Invoice
    from .payment import Payment

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    requested_by: Mapped[str] = mapped_column(String)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    risk_level: Mapped[str] = mapped_column(String)
    reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="approvals")
    payment: Mapped[List["Payment"]] = relationship(back_populates="approval")

from __future__ import annotations

import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid import uuid4

from .base import Base

if TYPE_CHECKING:
    from .invoice import Invoice
    from .approval import Approval

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("approvals.id"), nullable=True)
    payment_reference: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    status: Mapped[str] = mapped_column(String, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
    approval: Mapped[Optional["Approval"]] = relationship(back_populates="payment")

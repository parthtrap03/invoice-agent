from __future__ import annotations

import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .purchase_order import PurchaseOrder
    from .invoice import Invoice

class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    vendor_code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    contact_email: Mapped[str] = mapped_column(String)
    tax_id: Mapped[str] = mapped_column(String)
    risk_score: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(back_populates="vendor")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="vendor")

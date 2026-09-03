from __future__ import annotations

import uuid
from typing import List, Optional, TYPE_CHECKING
from datetime import date, datetime
from sqlalchemy import String, Numeric, ForeignKey, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid import uuid4

from .base import Base

if TYPE_CHECKING:
    from .vendor import Vendor
    from .invoice import Invoice

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    po_number: Mapped[str] = mapped_column(String, unique=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"))
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    issue_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    department: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    vendor: Mapped["Vendor"] = relationship(back_populates="purchase_orders")
    items: Mapped[List["PurchaseOrderItem"]] = relationship(back_populates="purchase_order")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="purchase_order")

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    po_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"))
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(15, 2))
    total_price: Mapped[float] = mapped_column(Numeric(15, 2))

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")

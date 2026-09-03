from __future__ import annotations

import uuid
from typing import List, Optional, Any, TYPE_CHECKING
from datetime import date
from sqlalchemy import String, Numeric, ForeignKey, Date, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor
    from .purchase_order import PurchaseOrder
    from .approval import Approval
    from .payment import Payment
    from .agent import AgentRun

class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_number: Mapped[str] = mapped_column(String, unique=True)
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    po_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    
    subtotal: Mapped[float] = mapped_column(Numeric(15, 2))
    tax_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str] = mapped_column(String)
    
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    ai_decision: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    extracted_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    validation_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    po_match_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    duplicate_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    vendor_risk_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    decision_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    source_file_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="invoices")
    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship(back_populates="invoices")
    items: Mapped[List["InvoiceItem"]] = relationship(back_populates="invoice")
    approvals: Mapped[List["Approval"]] = relationship(back_populates="invoice")
    payments: Mapped[List["Payment"]] = relationship(back_populates="invoice")
    agent_runs: Mapped[List["AgentRun"]] = relationship(back_populates="invoice")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(15, 2))
    total_price: Mapped[float] = mapped_column(Numeric(15, 2))

    invoice: Mapped["Invoice"] = relationship(back_populates="items")

class InvoiceMatch(Base, TimestampMixin):
    __tablename__ = "invoice_matches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    matched_invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    match_type: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    match_details: Mapped[Any] = mapped_column(JSON)

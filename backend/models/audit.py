from __future__ import annotations

import uuid
from typing import Optional, Any
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from uuid import uuid4

from .base import Base

class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    user_name: Mapped[str] = mapped_column(String, default="demo_user")
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

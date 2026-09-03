from __future__ import annotations

import uuid
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, ForeignKey, Float, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid import uuid4

from .base import Base

if TYPE_CHECKING:
    from .invoice import Invoice

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    workflow_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="RUNNING")
    final_state: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    total_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="agent_runs")
    steps: Mapped[List["AgentStep"]] = relationship(back_populates="run")

class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"))
    agent_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    input_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    step_order: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    run: Mapped["AgentRun"] = relationship(back_populates="steps")

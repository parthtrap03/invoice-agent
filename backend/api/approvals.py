from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID
import math
from datetime import datetime, timezone

import uuid as uuid_module

from backend.database import get_db
from backend.models import Approval, Audit, Invoice, Payment
from backend.schemas import PaginatedResponse, ApprovalResponse, ApprovalActionRequest

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])


async def _load_approval(db: AsyncSession, approval_id: UUID | None = None, status_filter: str | None = None, page: int = 1, page_size: int = 20):
    """Helper to load approvals with related invoice + vendor data."""
    query = select(Approval).options(
        selectinload(Approval.invoice).selectinload(Invoice.vendor)
    )
    if approval_id:
        query = query.where(Approval.id == approval_id)
    if status_filter:
        query = query.where(Approval.status == status_filter)

    return query


def _to_response(app: Approval) -> ApprovalResponse:
    inv = app.invoice if hasattr(app, 'invoice') and app.invoice else None
    vendor_name = None
    if inv and hasattr(inv, 'vendor') and inv.vendor:
        vendor_name = inv.vendor.name
    return ApprovalResponse(
        id=app.id,
        invoice_id=app.invoice_id,
        requested_by=app.requested_by,
        approved_by=app.approved_by,
        status=app.status,
        risk_level=app.risk_level,
        reasons=app.reasons,
        evidence=app.evidence,
        comments=app.comments,
        requested_at=app.requested_at,
        decided_at=app.decided_at,
        invoice_number=inv.invoice_number if inv else None,
        vendor_name=vendor_name,
        total_amount=float(inv.total_amount) if inv else None,
    )


@router.get("/", response_model=PaginatedResponse[ApprovalResponse])
async def list_approvals(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    # Count
    count_q = select(func.count(Approval.id)).where(Approval.status == "PENDING")
    total_count = await db.scalar(count_q) or 0
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    # Fetch with eager loading
    query = (
        select(Approval)
        .options(selectinload(Approval.invoice).selectinload(Invoice.vendor))
        .where(Approval.status == "PENDING")
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    approvals = list(result.scalars().all())

    return PaginatedResponse(
        items=[_to_response(a) for a in approvals],
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(approval_id: UUID, db: AsyncSession = Depends(get_db)):
    query = (
        select(Approval)
        .where(Approval.id == approval_id)
        .options(selectinload(Approval.invoice).selectinload(Invoice.vendor))
    )
    result = await db.execute(query)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=404, detail="Approval not found")

    app.status = "APPROVED"
    app.decided_at = datetime.now(timezone.utc)
    app.approved_by = "demo_user"

    # Manual approval clears the invoice and initiates payment
    invoice = app.invoice
    payment_reference = None
    if invoice is not None:
        invoice.status = "APPROVED"
        payment_reference = f"PAY-{uuid_module.uuid4().hex[:8].upper()}"
        db.add(Payment(
            invoice_id=invoice.id,
            approval_id=app.id,
            payment_reference=payment_reference,
            amount=invoice.total_amount,
            currency=invoice.currency or "INR",
            status="INITIATED",
        ))
        db.add(Audit(
            user_name=app.approved_by,
            invoice_id=invoice.id,
            action="INVOICE_APPROVED_MANUALLY",
            entity_type="Approval",
            entity_id=app.id,
            details={
                "invoice_number": invoice.invoice_number,
                "amount": float(invoice.total_amount or 0),
                "payment_reference": payment_reference,
            },
        ))

    await db.commit()

    # Re-load relationships
    query2 = (
        select(Approval)
        .where(Approval.id == approval_id)
        .options(selectinload(Approval.invoice).selectinload(Invoice.vendor))
    )
    result2 = await db.execute(query2)
    app = result2.scalar_one()

    return _to_response(app)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(approval_id: UUID, body: ApprovalActionRequest, db: AsyncSession = Depends(get_db)):
    query = (
        select(Approval)
        .where(Approval.id == approval_id)
        .options(selectinload(Approval.invoice).selectinload(Invoice.vendor))
    )
    result = await db.execute(query)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=404, detail="Approval not found")

    app.status = "REJECTED"
    app.decided_at = datetime.now(timezone.utc)
    app.approved_by = "demo_user"
    app.comments = body.comments

    invoice = app.invoice
    if invoice is not None:
        invoice.status = "REJECTED"
        db.add(Audit(
            user_name=app.approved_by,
            invoice_id=invoice.id,
            action="INVOICE_REJECTED_MANUALLY",
            entity_type="Approval",
            entity_id=app.id,
            details={
                "invoice_number": invoice.invoice_number,
                "comments": body.comments,
            },
        ))

    await db.commit()

    query2 = (
        select(Approval)
        .where(Approval.id == approval_id)
        .options(selectinload(Approval.invoice).selectinload(Invoice.vendor))
    )
    result2 = await db.execute(query2)
    app = result2.scalar_one()

    return _to_response(app)

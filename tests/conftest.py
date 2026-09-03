from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models import (
    Base,
    Invoice,
    InvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Vendor,
)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def make_vendor(
    name: str = "Test Vendor",
    code: str | None = None,
    status: str = "ACTIVE",
    is_active: bool = True,
    risk_score: float = 10,
) -> Vendor:
    return Vendor(
        id=uuid.uuid4(),
        vendor_code=code or f"VEND-{uuid.uuid4().hex[:6].upper()}",
        name=name,
        category="IT Services",
        status=status,
        contact_email="billing@test.in",
        tax_id=f"GST-{uuid.uuid4().hex[:9].upper()}",
        risk_score=Decimal(str(risk_score)),
        is_active=is_active,
    )


def make_po(
    vendor: Vendor,
    po_number: str,
    total: str,
    status: str = "ACTIVE",
    items: list[tuple[str, int, str]] | None = None,
) -> tuple[PurchaseOrder, list[PurchaseOrderItem]]:
    po = PurchaseOrder(
        id=uuid.uuid4(),
        po_number=po_number,
        vendor_id=vendor.id,
        total_amount=Decimal(total),
        currency="INR",
        status=status,
        issue_date=date.today() - timedelta(days=30),
        department="IT",
    )
    po_items = [
        PurchaseOrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            description=desc,
            quantity=qty,
            unit_price=Decimal(unit),
            total_price=Decimal(unit) * qty,
        )
        for desc, qty, unit in (items or [])
    ]
    return po, po_items


def make_invoice(
    vendor: Vendor | None,
    invoice_number: str,
    subtotal: str,
    tax: str,
    total: str,
    po: PurchaseOrder | None = None,
    invoice_date: date | None = None,
    items: list[tuple[str, int, str]] | None = None,
) -> tuple[Invoice, list[InvoiceItem]]:
    inv = Invoice(
        id=uuid.uuid4(),
        invoice_number=invoice_number,
        vendor_id=vendor.id if vendor else None,
        po_id=po.id if po else None,
        subtotal=Decimal(subtotal),
        tax_amount=Decimal(tax),
        total_amount=Decimal(total),
        currency="INR",
        invoice_date=invoice_date or date.today(),
        due_date=date.today() + timedelta(days=30),
        payment_terms="NET30",
        status="EXTRACTED",
    )
    inv_items = [
        InvoiceItem(
            id=uuid.uuid4(),
            invoice_id=inv.id,
            description=desc,
            quantity=qty,
            unit_price=Decimal(unit),
            total_price=Decimal(unit) * qty,
        )
        for desc, qty, unit in (items or [])
    ]
    return inv, inv_items


async def persist(db: AsyncSession, *objects) -> None:
    for obj in objects:
        if isinstance(obj, (list, tuple)):
            db.add_all(obj)
        else:
            db.add(obj)
    await db.commit()

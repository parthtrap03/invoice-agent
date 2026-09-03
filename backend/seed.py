from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PurchaseOrder, PurchaseOrderItem, Vendor

"""Demo seed data.

Deliberately small and deterministic: four vendors (one inactive) and two
active purchase orders that the demo invoices in uploads/demo/ match against.

Invoices are NOT seeded - they are meant to be uploaded through the app so the
extraction and rules pipeline runs for real.
"""


async def seed_database(db: AsyncSession) -> None:
    """Populate the database with demo master data. Idempotent."""
    existing = await db.scalar(select(func.count()).select_from(Vendor))
    if existing:
        return

    vendors = _build_vendors()
    db.add_all(vendors)
    _add_purchase_orders(db, vendors)
    await db.commit()


def _build_vendors() -> list[Vendor]:
    def vendor(code: str, name: str, tax_id: str, risk: float, active: bool = True) -> Vendor:
        return Vendor(
            id=uuid.uuid4(),
            vendor_code=code,
            name=name,
            category="IT Services",
            status="ACTIVE" if active else "INACTIVE",
            contact_email=f"billing@{code.lower()}.in",
            tax_id=tax_id,
            risk_score=Decimal(str(risk)),
            is_active=active,
        )

    return [
        vendor("VEND-101", "Zenith IT Solutions", "27ZENITH9001Z1", 10),
        vendor("VEND-102", "ABC Cloud Services", "27ABCCLOUD02Z2", 15),
        vendor("VEND-103", "Deluxe Office Supplies", "27DELUXE003Z3", 20),
        vendor("VEND-104", "Phantom Traders", "27PHANTOM04Z4", 65, active=False),
    ]


def _add_purchase_orders(db: AsyncSession, vendors: list[Vendor]) -> None:
    by_code = {v.vendor_code: v for v in vendors}

    def add_po(number: str, vendor: Vendor, total: str, desc: str, qty: int, unit: str) -> None:
        po = PurchaseOrder(
            id=uuid.uuid4(),
            po_number=number,
            vendor_id=vendor.id,
            total_amount=Decimal(total),
            currency="INR",
            status="ACTIVE",
            issue_date=date.today() - timedelta(days=20),
            department="IT",
        )
        db.add(po)
        db.add(PurchaseOrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            description=desc,
            quantity=qty,
            unit_price=Decimal(unit),
            total_price=Decimal(unit) * qty,
        ))

    # Matches uploads/demo/01 exactly -> AUTO_APPROVE
    add_po("PO-5001", by_code["VEND-101"], "400000.00", "Software Development Services", 4, "100000.00")
    # uploads/demo/02 bills Rs.18,40,000 against this -> 2.22% variance -> REVIEW
    add_po("PO-99182", by_code["VEND-102"], "1800000.00", "Cloud Infrastructure Services", 12, "150000.00")

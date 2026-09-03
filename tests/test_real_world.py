from __future__ import annotations

"""End-to-end tests against the shipped demo invoices, plus the
approval -> payment flow."""

import os

import pytest
from sqlalchemy import select

from backend.api.approvals import approve_request
from backend.models import Approval, Audit, Payment
from backend.services.extraction_service import PDFTextExtractor
from tests.conftest import make_invoice, make_vendor, persist

DEMO_DIR = "uploads/demo"


def demo(name: str) -> str:
    return os.path.join(DEMO_DIR, name)


# ---------------------------------------------------------------------------
# Extraction against the demo PDFs the walkthrough depends on
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(DEMO_DIR), reason="run setup_demo.py first")
async def test_demo_invoice_fields_extracted():
    result = await PDFTextExtractor().extract(demo("02-po-variance-review.pdf"))

    assert result.invoice_number == "INV-88231"
    assert result.vendor_name == "ABC Cloud Services"
    assert result.po_number == "PO-99182"
    assert result.currency == "INR"
    assert result.payment_terms == "NET30"
    assert result.invoice_date is not None
    assert len(result.line_items) == 1
    assert result.line_items[0].quantity == 12
    # 12 x 153,333.33 = 1,839,999.96, taxed at 18%
    assert abs(result.subtotal - 1_840_000) < 1
    assert abs(result.tax_amount - 331_200) < 1
    assert abs(result.total_amount - 2_171_200) < 1


@pytest.mark.skipif(not os.path.isdir(DEMO_DIR), reason="run setup_demo.py first")
@pytest.mark.parametrize(
    "filename,invoice_number,gst_rate",
    [
        ("01-clean-auto-approve.pdf", "INV-2001", 0.18),
        ("03-wrong-gst-review.pdf", "INV-3003", 0.05),
        ("04-inactive-vendor-reject.pdf", "INV-4004", 0.18),
        ("05-duplicate-reject.pdf", "INV-5005", 0.18),
    ],
)
async def test_every_demo_invoice_parses(filename, invoice_number, gst_rate):
    """Each demo scenario must extract cleanly - the walkthrough depends on it."""
    result = await PDFTextExtractor().extract(demo(filename))

    assert result.invoice_number == invoice_number
    assert result.vendor_name
    assert result.subtotal and result.tax_amount and result.total_amount
    assert abs(result.tax_amount - result.subtotal * gst_rate) < 1
    assert abs(result.total_amount - (result.subtotal + result.tax_amount)) < 1


# ---------------------------------------------------------------------------
# Approval -> Payment flow
# ---------------------------------------------------------------------------
async def test_manual_approval_creates_payment(db):
    vendor = make_vendor("PayMe Ltd")
    inv, items = make_invoice(vendor, "INV-PAY-1", "200000.00", "36000.00", "236000.00")
    inv.status = "REVIEW_REQUIRED"
    approval = Approval(
        invoice_id=inv.id,
        requested_by="rules_engine",
        status="PENDING",
        risk_level="MEDIUM",
    )
    await persist(db, vendor, inv, items, approval)

    response = await approve_request(approval.id, db)
    assert response.status == "APPROVED"

    await db.refresh(inv)
    assert inv.status == "APPROVED"

    payment = (
        await db.execute(select(Payment).where(Payment.invoice_id == inv.id))
    ).scalars().one()
    assert payment.status == "INITIATED"
    assert float(payment.amount) == 236000.0
    assert payment.payment_reference.startswith("PAY-")
    assert payment.approval_id == approval.id

    audit = (
        await db.execute(select(Audit).where(Audit.invoice_id == inv.id))
    ).scalars().one()
    assert audit.action == "INVOICE_APPROVED_MANUALLY"
    assert audit.details["payment_reference"] == payment.payment_reference

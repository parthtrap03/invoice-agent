from __future__ import annotations

"""Phase 5 tests: real downloaded invoices, policy document ingestion,
finance Q&A, and the approval -> payment flow."""

import os

import pytest
from sqlalchemy import select

from backend.api.approvals import approve_request
from backend.models import Audit, Payment, Policy
from backend.services.extraction_service import PDFTextExtractor
from backend.services.finance_service import answer_finance_query
from backend.services.policy_service import ingest_policy_document, split_policy_sections
from tests.conftest import make_invoice, make_vendor, persist

SLICED = "uploads/samples/invoice-sliced.pdf"
CONTOSO = "uploads/samples/invoice-contoso.pdf"
UNFPA_POLICY = "uploads/policies/unfpa-accounts-payable-policy.pdf"


# ---------------------------------------------------------------------------
# Real invoice PDFs (downloaded samples)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.exists(SLICED), reason="sample invoice not downloaded")
async def test_real_invoice_sliced_extraction():
    result = await PDFTextExtractor().extract(SLICED)
    assert result.invoice_number == "INV-3337"
    assert result.vendor_name == "DEMO - Sliced Invoices"
    assert result.subtotal == 85.0
    assert result.tax_amount == 8.5
    assert result.total_amount == 93.5
    assert result.currency == "USD"
    assert result.invoice_date is not None and result.invoice_date.isoformat() == "2016-01-25"
    assert result.payment_terms == "NET30"  # from "due within 30 days" fallback


@pytest.mark.skipif(not os.path.exists(CONTOSO), reason="sample invoice not downloaded")
async def test_real_invoice_contoso_extraction():
    result = await PDFTextExtractor().extract(CONTOSO)
    assert result.invoice_number == "INV-100"
    assert result.po_number == "PO-3333"
    assert result.subtotal == 100.0
    assert result.tax_amount == 10.0
    assert result.total_amount == 110.0
    assert result.invoice_date is not None and result.invoice_date.isoformat() == "2019-11-15"


# ---------------------------------------------------------------------------
# Policy document ingestion
# ---------------------------------------------------------------------------
SYNTHETIC_POLICY = """
ACCOUNTS PAYABLE POLICY

1. PURPOSE AND SCOPE
This policy establishes the framework for processing vendor invoices and
ensuring timely, accurate and authorized payments across the organization.

2. INVOICE APPROVAL THRESHOLDS
All invoices exceeding the approval threshold require managerial sign-off.
Invoices below the threshold may be auto-approved when all validations pass.

3. DUPLICATE PAYMENTS
The system must detect and prevent duplicate payments to vendors using
exact and fuzzy matching on invoice number, amount and dates.
"""


def test_split_policy_sections_synthetic():
    sections = split_policy_sections(SYNTHETIC_POLICY)
    titles = [t for t, _ in sections]
    assert "Purpose And Scope" in titles
    assert "Invoice Approval Thresholds" in titles
    assert "Duplicate Payments" in titles
    for _, content in sections:
        assert len(content) >= 60


@pytest.mark.skipif(not os.path.exists(UNFPA_POLICY), reason="policy PDF not downloaded")
async def test_ingest_real_policy_document(db):
    created = await ingest_policy_document(db, UNFPA_POLICY, category="Accounts Payable")
    assert len(created) >= 3
    assert all(p.policy_code.startswith("DOC-UNFPA") for p in created)

    # Re-ingesting replaces, not duplicates
    created2 = await ingest_policy_document(db, UNFPA_POLICY, category="Accounts Payable")
    total = (await db.execute(select(Policy))).scalars().all()
    assert len(total) == len(created2)


# ---------------------------------------------------------------------------
# Finance Q&A (deterministic, database-backed)
# ---------------------------------------------------------------------------
async def test_finance_query_total_spend(db):
    vendor = make_vendor("SpendCo")
    inv1, items1 = make_invoice(vendor, "INV-SP-1", "100000.00", "18000.00", "118000.00")
    inv1.status = "APPROVED"
    inv2, items2 = make_invoice(vendor, "INV-SP-2", "50000.00", "9000.00", "59000.00")
    inv2.status = "APPROVED"
    inv3, items3 = make_invoice(vendor, "INV-SP-3", "999.00", "179.82", "1178.82")
    inv3.status = "REJECTED"  # not counted
    await persist(db, vendor, inv1, inv2, inv3)

    result = await answer_finance_query(db, "How much have we spent in total?")
    assert result.data[0]["invoice_count"] == 2
    assert result.data[0]["total_spend"] == 177000.0
    assert "₹177,000.00" in result.answer


async def test_finance_query_policies(db):
    db.add(Policy(
        policy_code="POL-TEST-01", title="Duplicate Invoice Detection",
        category="Finance", content="Duplicate invoices must be rejected automatically.",
        version="1.0", is_active=True,
    ))
    await db.commit()

    result = await answer_finance_query(db, "what is our duplicate invoice policy?")
    assert result.data and result.data[0]["policy_code"] == "POL-TEST-01"
    assert "policy_search" in result.tools_used


async def test_finance_query_status_breakdown(db):
    vendor = make_vendor("StatusCo")
    inv, _ = make_invoice(vendor, "INV-ST-1", "1000.00", "180.00", "1180.00")
    inv.status = "APPROVED"
    await persist(db, vendor, inv)

    result = await answer_finance_query(db, "give me the invoice status breakdown")
    assert any(d["status"] == "APPROVED" and d["count"] == 1 for d in result.data)


# ---------------------------------------------------------------------------
# Approval -> Payment flow
# ---------------------------------------------------------------------------
async def test_manual_approval_creates_payment(db):
    from backend.models import Approval

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

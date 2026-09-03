from __future__ import annotations

"""Comprehensive tests for the deterministic financial rules engine (Phase 3)."""

from datetime import date

from sqlalchemy import select

from backend.models import Approval
from backend.rules.engine import FinanceRulesEngine
from tests.conftest import make_invoice, make_po, make_vendor, persist


# ---------------------------------------------------------------------------
# Test 1: Clean invoice with matching PO -> AUTO_APPROVE
# ---------------------------------------------------------------------------
async def test_clean_invoice_auto_approved(db):
    vendor = make_vendor("Clean Vendor Co", risk_score=10)
    po, po_items = make_po(
        vendor, "PO-10001", "100000.00",
        items=[("Consulting Services", 2, "50000.00")],
    )
    inv, inv_items = make_invoice(
        vendor, "INV-CLEAN-001",
        subtotal="100000.00", tax="18000.00", total="118000.00",
        po=po, items=[("Consulting Services", 2, "50000.00")],
    )
    await persist(db, vendor, po, po_items, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.decision == "AUTO_APPROVE"
    assert result.risk_score < 30
    assert result.risk_level == "LOW"
    assert result.status == "APPROVED"
    assert result.validation_result["valid"] is True
    assert result.po_match_result["matched"] is True
    assert result.duplicate_result["duplicate"] is False
    assert result.approval_created is False

    # Persisted onto the invoice row
    await db.refresh(inv)
    assert inv.status == "APPROVED"
    assert inv.ai_decision == "AUTO_APPROVE"


# ---------------------------------------------------------------------------
# Test 2: Primary demo scenario INV-88231 -> REVIEW_REQUIRED
#   PO-99182 = ₹18,00,000, invoice subtotal ₹18,40,000 => 2.22% variance
#   Total ₹21,71,200 > ₹10,00,000 approval threshold
# ---------------------------------------------------------------------------
async def test_demo_invoice_88231_review_required(db):
    vendor = make_vendor("ABC Cloud Services", code="VEND-001", risk_score=15)
    po, po_items = make_po(
        vendor, "PO-99182", "1800000.00",
        items=[("Cloud Infrastructure Services", 12, "150000.00")],
    )
    inv, inv_items = make_invoice(
        vendor, "INV-88231",
        subtotal="1840000.00", tax="331200.00", total="2171200.00",
        po=po, items=[("Cloud Infrastructure Services", 12, "153333.33")],
    )
    await persist(db, vendor, po, po_items, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.decision == "REVIEW_REQUIRED"
    assert result.status == "REVIEW_REQUIRED"
    # PO variance (30) + approval threshold (25); spec expects risk ≈ 55–67
    assert 50 <= result.risk_score <= 70
    assert result.po_match_result["variance_pct"] == 2.22
    assert result.po_match_result["variance_acceptable"] is False
    assert result.decision_result["above_approval_threshold"] is True
    assert result.validation_result["valid"] is True  # 18% GST is correct
    assert any("variance" in r.lower() for r in result.reasons)
    assert any("threshold" in r.lower() for r in result.reasons)

    # A pending approval must be opened automatically
    assert result.approval_created is True
    approval = (
        await db.execute(select(Approval).where(Approval.invoice_id == inv.id))
    ).scalars().first()
    assert approval is not None
    assert approval.status == "PENDING"
    assert approval.requested_by == "rules_engine"

    # Re-running must not create a second pending approval
    result2 = await FinanceRulesEngine().evaluate_invoice(db, inv.id)
    assert result2.approval_created is False


# ---------------------------------------------------------------------------
# Test 3: Duplicate invoice -> REJECT with risk > 80
# ---------------------------------------------------------------------------
async def test_duplicate_invoice_rejected(db):
    vendor = make_vendor("Dup Vendor Ltd", risk_score=12)
    original, orig_items = make_invoice(
        vendor, "INV-DUP-100",
        subtotal="500000.00", tax="90000.00", total="590000.00",
        invoice_date=date.today(),
        items=[("Managed Services", 1, "500000.00")],
    )
    duplicate, dup_items = make_invoice(
        vendor, "INV-DUP-100-B",
        subtotal="500000.00", tax="90000.00", total="590000.00",
        invoice_date=date.today(),
        items=[("Managed Services", 1, "500000.00")],
    )
    await persist(db, vendor, original, orig_items, duplicate, dup_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, duplicate.id)

    assert result.decision == "REJECT"
    assert result.status == "REJECTED"
    assert result.risk_score > 80
    assert result.risk_level == "HIGH"
    assert result.duplicate_result["duplicate"] is True
    assert result.duplicate_result["confidence"] >= 0.85
    assert result.duplicate_result["matched_invoice"] == "INV-DUP-100"
    assert result.approval_created is False


# ---------------------------------------------------------------------------
# Test 4: Inactive vendor -> REJECT with risk > 80
# ---------------------------------------------------------------------------
async def test_inactive_vendor_rejected(db):
    vendor = make_vendor("Ghost Corp", status="INACTIVE", is_active=False, risk_score=65)
    inv, inv_items = make_invoice(
        vendor, "INV-INACTIVE-001",
        subtotal="100000.00", tax="18000.00", total="118000.00",
        items=[("Services", 1, "100000.00")],
    )
    await persist(db, vendor, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.decision == "REJECT"
    assert result.status == "REJECTED"
    assert result.risk_score > 80
    assert result.risk_level == "HIGH"
    assert result.vendor_risk_result["active"] is False
    assert any("inactive" in r.lower() for r in result.reasons)


# ---------------------------------------------------------------------------
# Test 5: Tax mismatch (5% instead of 18%) -> REVIEW_REQUIRED
# ---------------------------------------------------------------------------
async def test_tax_mismatch_review_required(db):
    vendor = make_vendor("TaxErr Traders", risk_score=10)
    inv, inv_items = make_invoice(
        vendor, "INV-TAX-BAD-001",
        subtotal="100000.00", tax="5000.00", total="105000.00",
        items=[("Office Supplies", 1, "100000.00")],
    )
    await persist(db, vendor, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.decision == "REVIEW_REQUIRED"
    assert result.status == "REVIEW_REQUIRED"
    assert result.validation_result["valid"] is False
    assert result.validation_result["gst_correct"] is False
    assert "TAX_DISCREPANCY" in result.decision_result["violations"]
    assert any("tax" in r.lower() for r in result.reasons)
    assert result.approval_created is True


# ---------------------------------------------------------------------------
# Additional edge coverage
# ---------------------------------------------------------------------------
async def test_high_value_without_po_review_required(db):
    """> ₹10L with no PO: threshold violation alone forces review."""
    vendor = make_vendor("BigDeal Inc", risk_score=8)
    inv, inv_items = make_invoice(
        vendor, "INV-HV-001",
        subtotal="1500000.00", tax="270000.00", total="1770000.00",
        items=[("Enterprise License", 1, "1500000.00")],
    )
    await persist(db, vendor, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.decision == "REVIEW_REQUIRED"
    assert result.po_match_result["po_found"] is False
    assert result.decision_result["above_approval_threshold"] is True


async def test_totals_arithmetic_mismatch_flagged(db):
    """subtotal + tax != total must fail validation."""
    vendor = make_vendor("MathsOff LLP", risk_score=10)
    inv, inv_items = make_invoice(
        vendor, "INV-ARITH-001",
        subtotal="100000.00", tax="18000.00", total="120000.00",  # off by 2000
        items=[("Services", 1, "100000.00")],
    )
    await persist(db, vendor, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.validation_result["totals_match"] is False
    assert result.decision == "REVIEW_REQUIRED"


async def test_high_risk_vendor_flagged(db):
    """Active vendor with risk_score > 70 adds vendor risk points."""
    vendor = make_vendor("Shady Systems", risk_score=85)
    inv, inv_items = make_invoice(
        vendor, "INV-RISKY-001",
        subtotal="50000.00", tax="9000.00", total="59000.00",
        items=[("Services", 1, "50000.00")],
    )
    await persist(db, vendor, inv, inv_items)

    result = await FinanceRulesEngine().evaluate_invoice(db, inv.id)

    assert result.vendor_risk_result["high_risk"] is True
    assert "VENDOR_RISK" in result.decision_result["violations"]
    assert result.decision == "REVIEW_REQUIRED"  # active vendor, so not a hard fail

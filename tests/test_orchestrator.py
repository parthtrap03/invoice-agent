from __future__ import annotations

"""Tests for Phase 4: agent orchestration (AgentRun/AgentStep tracing),
policy compliance results, and audit trail entries."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from backend.models import AgentRun, AgentStep, Audit, Invoice
from backend.services.orchestrator import InvoiceProcessingOrchestrator
from tests.conftest import make_invoice, make_po, make_vendor, persist

EXPECTED_STEPS = [
    "Extraction",
    "Validation",
    "PO Matching",
    "Duplicate Detection",
    "Vendor Risk",
    "Decision",
]


async def _demo_scenario(db):
    """INV-88231-style scenario: 2.22% variance + above ₹10L threshold."""
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
    return inv


async def test_orchestrator_creates_full_trace(db):
    inv = await _demo_scenario(db)

    run, result = await InvoiceProcessingOrchestrator().process_invoice(db, inv.id)

    assert run.status == "COMPLETED"
    assert run.workflow_type == "invoice_processing"
    assert run.invoice_id == inv.id
    assert run.completed_at is not None
    assert run.final_state["decision"] == "REVIEW_REQUIRED"
    assert run.final_state["risk_score"] == result.risk_score

    steps = (
        await db.execute(
            select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.step_order)
        )
    ).scalars().all()
    assert [s.agent_name for s in steps] == EXPECTED_STEPS
    assert all(s.tokens_used == 0 for s in steps)  # deterministic pipeline, no LLM

    # Already-extracted invoice => extraction step is SKIPPED, rest COMPLETED
    assert steps[0].status == "SKIPPED"
    assert all(s.status == "COMPLETED" for s in steps[1:])
    assert steps[2].output_data["variance_pct"] == 2.22


async def test_orchestrator_runs_extraction_for_uploaded_invoice(db, tmp_path):
    """An UPLOADED invoice with a source file goes through extraction first."""
    vendor = make_vendor("ABC Cloud Services", code="VEND-001", risk_score=15)
    po, po_items = make_po(
        vendor, "PO-99182", "1800000.00",
        items=[("Cloud Infrastructure Services", 12, "150000.00")],
    )
    fake_file = tmp_path / "INV-88231.pdf"
    fake_file.write_text("demo")
    inv = Invoice(
        id=uuid.uuid4(),
        invoice_number="UPLOAD-INV-88231.pdf",
        invoice_date=date.today(),
        payment_terms="NET30",
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("0"),
        status="UPLOADED",
        source_file_key=str(fake_file),
    )
    await persist(db, vendor, po, po_items, inv)

    run, result = await InvoiceProcessingOrchestrator().process_invoice(db, inv.id)

    # Mock adapter recognized the demo file, vendor+PO resolved, rules ran
    await db.refresh(inv)
    assert inv.invoice_number == "INV-88231"
    assert inv.vendor_id == vendor.id
    assert inv.po_id == po.id
    assert float(inv.total_amount) == 2171200.00
    assert result.decision == "REVIEW_REQUIRED"

    steps = (
        await db.execute(
            select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.step_order)
        )
    ).scalars().all()
    assert steps[0].agent_name == "Extraction"
    assert steps[0].status == "COMPLETED"
    assert steps[0].output_data["method"] == "mock"
    assert steps[0].output_data["po_number"] == "PO-99182"


async def test_audit_entries_written_with_trace_id(db):
    inv = await _demo_scenario(db)

    run, _ = await InvoiceProcessingOrchestrator().process_invoice(db, inv.id)

    audits = (
        await db.execute(select(Audit).where(Audit.invoice_id == inv.id))
    ).scalars().all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "INVOICE_REVIEW_REQUESTED"
    assert audit.user_name == "rules_engine"
    assert audit.trace_id == str(run.id)
    assert audit.details["decision"] == "REVIEW_REQUIRED"
    assert audit.details["approval_created"] is True


async def test_clean_invoice_audit_action_auto_approved(db):
    vendor = make_vendor("Clean Vendor Co", risk_score=10)
    po, po_items = make_po(vendor, "PO-20001", "100000.00", items=[("Consulting", 2, "50000.00")])
    inv, inv_items = make_invoice(
        vendor, "INV-CLEAN-P4",
        subtotal="100000.00", tax="18000.00", total="118000.00",
        po=po, items=[("Consulting", 2, "50000.00")],
    )
    await persist(db, vendor, po, po_items, inv, inv_items)

    run, result = await InvoiceProcessingOrchestrator().process_invoice(db, inv.id)

    assert result.decision == "AUTO_APPROVE"
    audit = (
        await db.execute(select(Audit).where(Audit.invoice_id == inv.id))
    ).scalars().one()
    assert audit.action == "INVOICE_AUTO_APPROVED"
    assert run.final_state["decision"] == "AUTO_APPROVE"


async def test_failed_run_marked_failed(db):
    """Unknown invoice id inside a run context raises; run rows only exist for real invoices,
    so here we assert the orchestrator surfaces the error cleanly."""
    try:
        await InvoiceProcessingOrchestrator().process_invoice(db, uuid.uuid4())
        assert False, "expected ValueError"
    except ValueError:
        pass
    runs = (await db.execute(select(AgentRun))).scalars().all()
    assert runs == []  # no orphan runs for nonexistent invoices

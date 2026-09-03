from __future__ import annotations

"""Main orchestrator of the deterministic financial rules engine (Phase 3).

Runs every validator against an invoice, persists structured results onto the
invoice row, updates status/risk/decision, opens a pending Approval when the
decision is REVIEW_REQUIRED, and writes an Audit entry for the decision.

An optional `recorder` callback receives one event per pipeline step so a
caller (e.g. the agent orchestrator) can persist AgentStep traces.
"""

from time import perf_counter
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Approval, Audit, Invoice, PurchaseOrder
from backend.rules.config import RulesConfig, get_rules_config
from backend.rules.duplicate_detector import detect_duplicates
from backend.rules.po_matcher import match_purchase_order
from backend.rules.risk_scorer import score_risk
from backend.rules.tax_validator import validate_taxes
from backend.rules.vendor_checker import check_vendor

_STATUS_BY_DECISION = {
    "AUTO_APPROVE": "APPROVED",
    "REVIEW_REQUIRED": "REVIEW_REQUIRED",
    "REJECT": "REJECTED",
}

_AUDIT_ACTION_BY_DECISION = {
    "AUTO_APPROVE": "INVOICE_AUTO_APPROVED",
    "REVIEW_REQUIRED": "INVOICE_REVIEW_REQUESTED",
    "REJECT": "INVOICE_REJECTED",
}

# (step_name, status, output, duration_ms)
StepRecorder = Callable[[str, str, dict[str, Any], float], Awaitable[None]]


class RuleEvaluationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID
    invoice_number: Optional[str] = None
    decision: str
    risk_score: int
    risk_level: str
    status: str
    reasons: list[str] = []
    validation_result: dict[str, Any]
    po_match_result: dict[str, Any]
    duplicate_result: dict[str, Any]
    vendor_risk_result: dict[str, Any]
    decision_result: dict[str, Any]
    approval_created: bool = False


class FinanceRulesEngine:
    """Deterministic evaluation pipeline — no LLM involvement in math/rules."""

    def __init__(self, config: RulesConfig | None = None):
        self.config = config or get_rules_config()

    async def evaluate_invoice(
        self,
        db: AsyncSession,
        invoice_id: UUID,
        recorder: StepRecorder | None = None,
        trace_id: str | None = None,
    ) -> RuleEvaluationResult:
        invoice = await self._load_invoice(db, invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice {invoice_id} not found")

        po = await self._load_po(db, invoice)
        vendor = invoice.vendor
        total_amount = float(invoice.total_amount or 0)

        t0 = perf_counter()
        validation_result = validate_taxes(invoice, self.config)
        await self._record(recorder, "Validation", validation_result, t0)

        t0 = perf_counter()
        po_match_result = match_purchase_order(invoice, po, self.config)
        await self._record(recorder, "PO Matching", po_match_result, t0)

        t0 = perf_counter()
        duplicate_result = await detect_duplicates(db, invoice, self.config)
        await self._record(recorder, "Duplicate Detection", duplicate_result, t0)

        t0 = perf_counter()
        vendor_risk_result = check_vendor(vendor, self.config)
        await self._record(recorder, "Vendor Risk", vendor_risk_result, t0)

        t0 = perf_counter()
        decision_result = score_risk(
            total_amount=total_amount,
            validation_result=validation_result,
            po_match_result=po_match_result,
            duplicate_result=duplicate_result,
            vendor_result=vendor_risk_result,
            config=self.config,
        )
        await self._record(recorder, "Decision", decision_result, t0)

        decision = decision_result["decision"]
        status = _STATUS_BY_DECISION[decision]

        invoice.validation_result = validation_result
        invoice.po_match_result = po_match_result
        invoice.duplicate_result = duplicate_result
        invoice.vendor_risk_result = vendor_risk_result
        invoice.decision_result = decision_result
        invoice.status = status
        invoice.risk_score = decision_result["risk_score"]
        invoice.risk_level = decision_result["risk_level"]
        invoice.ai_decision = decision

        approval_created = False
        if decision == "REVIEW_REQUIRED":
            approval_created = await self._ensure_pending_approval(db, invoice, decision_result, po_match_result)

        db.add(
            Audit(
                user_name="rules_engine",
                invoice_id=invoice.id,
                action=_AUDIT_ACTION_BY_DECISION[decision],
                entity_type="Invoice",
                entity_id=invoice.id,
                details={
                    "decision": decision,
                    "risk_score": decision_result["risk_score"],
                    "risk_level": decision_result["risk_level"],
                    "reasons": decision_result["reasons"],
                    "violations": decision_result["violations"],
                    "approval_created": approval_created,
                },
                trace_id=trace_id,
            )
        )

        await db.commit()
        await db.refresh(invoice)

        return RuleEvaluationResult(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            decision=decision,
            risk_score=decision_result["risk_score"],
            risk_level=decision_result["risk_level"],
            status=status,
            reasons=decision_result["reasons"],
            validation_result=validation_result,
            po_match_result=po_match_result,
            duplicate_result=duplicate_result,
            vendor_risk_result=vendor_risk_result,
            decision_result=decision_result,
            approval_created=approval_created,
        )

    @staticmethod
    async def _record(
        recorder: StepRecorder | None,
        name: str,
        output: dict[str, Any],
        t0: float,
    ) -> None:
        if recorder is not None:
            await recorder(name, "COMPLETED", output, (perf_counter() - t0) * 1000)

    async def _load_invoice(self, db: AsyncSession, invoice_id: UUID) -> Invoice | None:
        query = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.vendor),
                selectinload(Invoice.items),
                selectinload(Invoice.purchase_order).selectinload(PurchaseOrder.items),
            )
        )
        return (await db.execute(query)).scalar_one_or_none()

    async def _load_po(self, db: AsyncSession, invoice: Invoice) -> PurchaseOrder | None:
        if invoice.purchase_order is not None:
            return invoice.purchase_order

        # Fall back to the PO number captured during extraction
        po_number = (invoice.extracted_data or {}).get("po_number") if isinstance(invoice.extracted_data, dict) else None
        if not po_number:
            return None
        query = (
            select(PurchaseOrder)
            .where(PurchaseOrder.po_number == po_number)
            .options(selectinload(PurchaseOrder.items))
        )
        po = (await db.execute(query)).scalar_one_or_none()
        if po is not None:
            invoice.po_id = po.id
        return po

    async def _ensure_pending_approval(
        self,
        db: AsyncSession,
        invoice: Invoice,
        decision_result: dict[str, Any],
        po_match_result: dict[str, Any],
    ) -> bool:
        existing = (
            await db.execute(
                select(Approval).where(
                    Approval.invoice_id == invoice.id,
                    Approval.status == "PENDING",
                )
            )
        ).scalars().first()
        if existing is not None:
            return False

        evidence_parts = []
        if po_match_result.get("po_found"):
            evidence_parts.append(
                f"PO {po_match_result.get('po_number')} amount: ₹{po_match_result.get('po_amount', 0):,.2f} | "
                f"Invoice amount: ₹{po_match_result.get('invoice_amount', 0):,.2f} | "
                f"Variance: {po_match_result.get('variance_pct')}%"
            )

        approval = Approval(
            invoice_id=invoice.id,
            requested_by="rules_engine",
            status="PENDING",
            risk_level=decision_result["risk_level"],
            reasons="; ".join(decision_result["reasons"]) or None,
            evidence=" | ".join(evidence_parts) or None,
        )
        db.add(approval)
        return True

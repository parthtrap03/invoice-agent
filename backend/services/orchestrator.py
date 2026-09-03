from __future__ import annotations

"""Invoice processing orchestrator (Phase 4).

Wraps the full pipeline (extraction -> rules engine) in an AgentRun with one
AgentStep per stage, so every processed invoice gets a real, queryable trace
at /api/agent-runs/{run_id}/trace - not just the seeded demo data.

The pipeline is deterministic (no LLM), so steps carry tokens_used=0 and no
model_id; when Bedrock extraction lands, those fields light up naturally.
"""

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AgentRun, AgentStep, Audit, Invoice
from backend.rules.engine import FinanceRulesEngine, RuleEvaluationResult
from backend.services.extraction_service import ExtractionError, get_extraction_service
from backend.services.invoice_service import apply_extraction, get_invoice


def _utcnow() -> datetime:
    # DB columns are naive DateTime (server_default func.now()); keep values naive UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _StepRecorder:
    """Persists one AgentStep per recorded pipeline stage."""

    def __init__(self, db: AsyncSession, run_id: UUID):
        self.db = db
        self.run_id = run_id
        self.order = 0
        self.total_duration_ms = 0.0

    async def __call__(self, name: str, status: str, output: dict[str, Any], duration_ms: float) -> None:
        self.order += 1
        self.total_duration_ms += duration_ms
        now = _utcnow()
        self.db.add(
            AgentStep(
                run_id=self.run_id,
                agent_name=name,
                status=status,
                output_data=output,
                duration_ms=round(duration_ms, 2),
                tokens_used=0,
                step_order=self.order,
                started_at=now,
                completed_at=now,
            )
        )


class InvoiceProcessingOrchestrator:
    """End-to-end processing: extraction (if pending) + rules engine, traced."""

    def __init__(self, engine: FinanceRulesEngine | None = None):
        self.engine = engine or FinanceRulesEngine()
        self.extraction = get_extraction_service()

    async def process_invoice(self, db: AsyncSession, invoice_id: UUID) -> tuple[AgentRun, RuleEvaluationResult]:
        invoice = await get_invoice(db, invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice {invoice_id} not found")

        run = AgentRun(
            invoice_id=invoice.id,
            workflow_type="invoice_processing",
            status="RUNNING",
            started_at=_utcnow(),
        )
        db.add(run)
        await db.flush()
        recorder = _StepRecorder(db, run.id)

        try:
            invoice = await self._extraction_step(db, invoice, recorder)
            result = await self.engine.evaluate_invoice(
                db, invoice_id, recorder=recorder, trace_id=str(run.id)
            )
        except Exception as exc:
            run.status = "FAILED"
            run.completed_at = _utcnow()
            run.final_state = {"error": str(exc)}
            await db.commit()
            raise

        run.status = "COMPLETED"
        run.completed_at = _utcnow()
        run.total_duration_ms = round(recorder.total_duration_ms, 2)
        run.total_tokens = 0
        run.final_state = {
            "decision": result.decision,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "status": result.status,
            "reasons": result.reasons,
            "approval_created": result.approval_created,
        }
        await db.commit()
        return run, result

    async def _extraction_step(
        self, db: AsyncSession, invoice: Invoice, recorder: _StepRecorder
    ) -> Invoice:
        needs_extraction = invoice.status in ("UPLOADED", "EXTRACTION_FAILED") and invoice.source_file_key
        if not needs_extraction:
            await recorder(
                "Extraction", "SKIPPED",
                {"reason": f"Invoice already extracted (status: {invoice.status})"},
                0.0,
            )
            return invoice

        t0 = perf_counter()
        try:
            from backend.services.file_storage import materialize

            local_path = await materialize(db, invoice.source_file_key)
            if local_path is None:
                raise ExtractionError(f"Source document not found: {invoice.source_file_key}")
            extracted = await self.extraction.extract(local_path)
        except ExtractionError as exc:
            await recorder(
                "Extraction", "FAILED",
                {"error": str(exc), "file": invoice.source_file_key},
                (perf_counter() - t0) * 1000,
            )
            raise

        invoice = await apply_extraction(db, invoice, extracted)
        await recorder(
            "Extraction", "COMPLETED",
            {
                "file": invoice.source_file_key,
                "method": extracted.extraction_method,
                "invoice_number": extracted.invoice_number,
                "vendor_name": extracted.vendor_name,
                "po_number": extracted.po_number,
                "total_amount": extracted.total_amount,
                "line_items": len(extracted.line_items),
                "confidence": extracted.confidence,
            },
            (perf_counter() - t0) * 1000,
        )
        db.add(
            Audit(
                user_name="rules_engine",
                invoice_id=invoice.id,
                action="INVOICE_EXTRACTED",
                entity_type="Invoice",
                entity_id=invoice.id,
                details={
                    "method": extracted.extraction_method,
                    "invoice_number": extracted.invoice_number,
                    "confidence": extracted.confidence,
                },
                trace_id=str(recorder.run_id),
            )
        )
        return invoice

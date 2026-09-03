from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from backend.database import get_db
from backend.models import AgentRun

router = APIRouter(prefix="/api/agent-runs", tags=["Agent Runs"])

def _run_summary(run: AgentRun) -> dict:
    return {
        "id": str(run.id),
        "invoice_id": str(run.invoice_id) if run.invoice_id else None,
        "workflow_type": run.workflow_type,
        "status": run.status,
        "total_duration_ms": run.total_duration_ms,
        "total_tokens": run.total_tokens,
        "final_state": run.final_state,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }

@router.get("/")
async def list_agent_runs(invoice_id: UUID | None = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    query = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
    if invoice_id:
        query = query.where(AgentRun.invoice_id == invoice_id)
    runs = (await db.execute(query)).scalars().all()
    return [_run_summary(r) for r in runs]

@router.get("/{run_id}")
async def get_agent_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(AgentRun).where(AgentRun.id == run_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Agent Run not found")
    return run

@router.get("/{run_id}/trace")
async def get_agent_run_trace(run_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(AgentRun).where(AgentRun.id == run_id).options(selectinload(AgentRun.steps))
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Agent Run not found")

    payload = _run_summary(run)
    payload["steps"] = [
        {
            "step_order": s.step_order,
            "agent_name": s.agent_name,
            "status": s.status,
            "duration_ms": s.duration_ms,
            "tokens_used": s.tokens_used,
            "model_id": s.model_id,
            "input_data": s.input_data,
            "output_data": s.output_data,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in sorted(run.steps, key=lambda s: s.step_order)
    ]
    return payload

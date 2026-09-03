from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.database import get_db
from backend.models import Invoice, Approval

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

@router.get("/")
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    # Total invoices
    total_query = select(func.count(Invoice.id))
    total_invoices = await db.scalar(total_query) or 0
    
    # By status
    status_query = select(Invoice.status, func.count(Invoice.id)).group_by(Invoice.status)
    status_result = await db.execute(status_query)
    by_status = {row[0]: row[1] for row in status_result.all()}
    
    # Total amount
    amount_query = select(func.sum(Invoice.total_amount))
    total_amount = await db.scalar(amount_query) or 0.0
    
    # Avg risk score
    risk_query = select(func.avg(Invoice.risk_score)).where(Invoice.risk_score.isnot(None))
    avg_risk_score = await db.scalar(risk_query) or 0.0
    
    # High risk count
    high_risk_query = select(func.count(Invoice.id)).where(Invoice.risk_level == "HIGH")
    high_risk_count = await db.scalar(high_risk_query) or 0
    
    # Pending approvals
    pending_app_query = select(func.count(Approval.id)).where(Approval.status == "PENDING")
    pending_approvals = await db.scalar(pending_app_query) or 0
    
    # Automation rate
    auto_query = select(func.count(Invoice.id)).where(Invoice.ai_decision == "AUTO_APPROVE")
    auto_count = await db.scalar(auto_query) or 0
    automation_rate = (auto_count / total_invoices) if total_invoices > 0 else 0.0
    
    return {
        "total_invoices": total_invoices,
        "by_status": by_status,
        "total_amount": float(total_amount),
        "avg_risk_score": float(avg_risk_score),
        "high_risk_count": high_risk_count,
        "pending_approvals": pending_approvals,
        "automation_rate": float(automation_rate)
    }

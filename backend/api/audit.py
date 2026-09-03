from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import math
from backend.database import get_db
from backend.models import Audit

router = APIRouter(prefix="/api/audit", tags=["Audit"])

@router.get("/")
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    query = select(Audit).order_by(desc(Audit.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    logs = list(result.scalars().all())
    
    # Simple pagination wrapper for raw dict response
    return {
        "items": logs,
        "page": page,
        "page_size": page_size
    }

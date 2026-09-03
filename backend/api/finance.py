from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.finance import FinanceQueryRequest, FinanceQueryResponse
from backend.services.finance_service import answer_finance_query

router = APIRouter(prefix="/api/finance", tags=["Finance Analyst"])

@router.post("/query", response_model=FinanceQueryResponse)
async def analyze_finance_query(request: FinanceQueryRequest, db: AsyncSession = Depends(get_db)):
    return await answer_finance_query(db, request.question)

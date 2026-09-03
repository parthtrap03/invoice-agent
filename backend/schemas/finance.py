from __future__ import annotations
from typing import Optional, Any
from backend.schemas.common import BaseSchema

class FinanceQueryRequest(BaseSchema):
    question: str

class FinanceQueryResponse(BaseSchema):
    answer: str
    sql_query: Optional[str] = None
    data: Optional[list[dict[str, Any]]] = None
    tools_used: list[str] = []
    sources: list[str] = []
    trace_id: Optional[str] = None

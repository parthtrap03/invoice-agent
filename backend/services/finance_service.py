from __future__ import annotations

"""Finance Analyst Q&A (Phase 5) - deterministic, database-backed.

Routes a natural-language question to SQL aggregations by keyword intent.
No LLM: every number comes straight from the database, so answers are
exact and auditable. (An LLM layer can later rephrase these answers.)
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Approval, Invoice, Policy, Vendor
from backend.schemas.finance import FinanceQueryResponse


def _fmt(amount: float) -> str:
    return f"₹{amount:,.2f}"


async def answer_finance_query(db: AsyncSession, question: str) -> FinanceQueryResponse:
    response = await _route_query(db, question)

    # Optional free local LLM (Ollama): rephrase the exact computed answer
    # naturally. Numbers always come from SQL; if no local LLM, keep as-is.
    try:
        from backend.services.llm_service import rephrase_answer

        natural = await rephrase_answer(question, response.answer, response.data)
        if natural:
            response.answer = natural
            response.tools_used = [*response.tools_used, "local_llm_rephrase"]
    except Exception:
        pass  # never let the optional LLM layer break a deterministic answer

    return response


async def _route_query(db: AsyncSession, question: str) -> FinanceQueryResponse:
    q = question.lower()

    if any(k in q for k in ("pending approval", "awaiting approval", "need approval", "approval queue")):
        return await _pending_approvals(db)
    if any(k in q for k in ("top vendor", "highest vendor", "biggest vendor", "vendor spend", "spend by vendor")):
        return await _top_vendors(db)
    # Policy questions first: "duplicate invoice policy" must hit policy search
    if any(k in q for k in ("policy", "policies", "rule", "threshold", "compliance")):
        return await _policies(db, q)
    if any(k in q for k in ("duplicate",)):
        return await _duplicates(db)
    if any(k in q for k in ("high risk", "risky", "risk score")):
        return await _high_risk(db)
    if any(k in q for k in ("reject",)):
        return await _by_status(db, "REJECTED", "rejected")
    if any(k in q for k in ("status", "how many invoice", "invoice count", "breakdown")):
        return await _status_breakdown(db)
    if any(k in q for k in ("spend", "spent", "total amount", "how much", "expense")):
        return await _total_spend(db, q)

    return await _overview(db)


async def _total_spend(db: AsyncSession, q: str) -> FinanceQueryResponse:
    query = select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0)).where(
        Invoice.status.in_(("APPROVED", "COMPLETED", "PAID"))
    )
    period = ""
    if any(k in q for k in ("this month", "last 30", "past 30", "month")):
        cutoff = date.today() - timedelta(days=30)
        query = query.where(Invoice.invoice_date >= cutoff)
        period = " in the last 30 days"

    count, total = (await db.execute(query)).one()
    return FinanceQueryResponse(
        answer=f"Approved spend{period}: {_fmt(float(total))} across {count} invoices.",
        sql_query="SELECT COUNT(*), SUM(total_amount) FROM invoices WHERE status IN ('APPROVED','COMPLETED','PAID')",
        data=[{"invoice_count": count, "total_spend": float(total)}],
        tools_used=["sql_aggregation"],
        sources=["invoices"],
    )


async def _pending_approvals(db: AsyncSession) -> FinanceQueryResponse:
    rows = (
        await db.execute(
            select(Approval, Invoice)
            .join(Invoice, Approval.invoice_id == Invoice.id)
            .where(Approval.status == "PENDING")
            .order_by(Invoice.total_amount.desc())
            .limit(20)
        )
    ).all()
    data = [
        {
            "invoice_number": inv.invoice_number,
            "total_amount": float(inv.total_amount or 0),
            "risk_level": app.risk_level,
            "reasons": app.reasons,
        }
        for app, inv in rows
    ]
    total_value = sum(d["total_amount"] for d in data)
    return FinanceQueryResponse(
        answer=f"There are {len(data)} invoices pending approval, worth {_fmt(total_value)} in total.",
        sql_query="SELECT * FROM approvals JOIN invoices ... WHERE approvals.status = 'PENDING'",
        data=data,
        tools_used=["sql_aggregation"],
        sources=["approvals", "invoices"],
    )


async def _top_vendors(db: AsyncSession) -> FinanceQueryResponse:
    rows = (
        await db.execute(
            select(Vendor.name, func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0))
            .join(Invoice, Invoice.vendor_id == Vendor.id)
            .where(Invoice.status.in_(("APPROVED", "COMPLETED", "PAID")))
            .group_by(Vendor.name)
            .order_by(func.sum(Invoice.total_amount).desc())
            .limit(5)
        )
    ).all()
    data = [{"vendor": name, "invoices": cnt, "total_spend": float(total)} for name, cnt, total in rows]
    top = data[0] if data else None
    answer = (
        f"Top vendor by approved spend: {top['vendor']} ({_fmt(top['total_spend'])} across {top['invoices']} invoices)."
        if top else "No approved vendor spend found."
    )
    return FinanceQueryResponse(
        answer=answer,
        sql_query="SELECT vendor, SUM(total_amount) FROM invoices GROUP BY vendor ORDER BY 2 DESC LIMIT 5",
        data=data,
        tools_used=["sql_aggregation"],
        sources=["invoices", "vendors"],
    )


async def _duplicates(db: AsyncSession) -> FinanceQueryResponse:
    invoices = (
        await db.execute(select(Invoice).where(Invoice.status == "REJECTED"))
    ).scalars().all()
    dups = [
        inv for inv in invoices
        if isinstance(inv.duplicate_result, dict) and inv.duplicate_result.get("duplicate")
    ]
    data = [
        {
            "invoice_number": inv.invoice_number,
            "matched_invoice": inv.duplicate_result.get("matched_invoice"),
            "confidence": inv.duplicate_result.get("confidence"),
            "total_amount": float(inv.total_amount or 0),
        }
        for inv in dups
    ]
    return FinanceQueryResponse(
        answer=f"{len(data)} rejected invoices were flagged as duplicates.",
        data=data,
        tools_used=["sql_aggregation", "duplicate_analysis"],
        sources=["invoices"],
    )


async def _high_risk(db: AsyncSession) -> FinanceQueryResponse:
    rows = (
        await db.execute(
            select(Invoice)
            .where(Invoice.risk_score >= 61)
            .order_by(Invoice.risk_score.desc())
            .limit(20)
        )
    ).scalars().all()
    data = [
        {
            "invoice_number": inv.invoice_number,
            "risk_score": inv.risk_score,
            "risk_level": inv.risk_level,
            "status": inv.status,
            "total_amount": float(inv.total_amount or 0),
        }
        for inv in rows
    ]
    return FinanceQueryResponse(
        answer=f"{len(data)} invoices are HIGH risk (score >= 61).",
        sql_query="SELECT * FROM invoices WHERE risk_score >= 61 ORDER BY risk_score DESC",
        data=data,
        tools_used=["sql_aggregation"],
        sources=["invoices"],
    )


async def _by_status(db: AsyncSession, status: str, label: str) -> FinanceQueryResponse:
    count, total = (
        await db.execute(
            select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                Invoice.status == status
            )
        )
    ).one()
    return FinanceQueryResponse(
        answer=f"{count} invoices are {label}, totalling {_fmt(float(total))}.",
        sql_query=f"SELECT COUNT(*), SUM(total_amount) FROM invoices WHERE status = '{status}'",
        data=[{"status": status, "count": count, "total_amount": float(total)}],
        tools_used=["sql_aggregation"],
        sources=["invoices"],
    )


async def _status_breakdown(db: AsyncSession) -> FinanceQueryResponse:
    rows = (
        await db.execute(
            select(Invoice.status, func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0))
            .group_by(Invoice.status)
            .order_by(func.count(Invoice.id).desc())
        )
    ).all()
    data = [{"status": s, "count": c, "total_amount": float(t)} for s, c, t in rows]
    parts = ", ".join(f"{d['count']} {d['status']}" for d in data)
    return FinanceQueryResponse(
        answer=f"Invoice breakdown: {parts}.",
        sql_query="SELECT status, COUNT(*), SUM(total_amount) FROM invoices GROUP BY status",
        data=data,
        tools_used=["sql_aggregation"],
        sources=["invoices"],
    )


# BM25 lives in backend.rules.text_search (shared with the rules engine's
# policy-evidence lookup); aliased here for existing imports/tests.
from backend.rules.text_search import bm25_rank as _bm25_rank, tokenize as _tokenize  # noqa: E402


async def _policies(db: AsyncSession, q: str) -> FinanceQueryResponse:
    query = select(Policy).where(Policy.is_active == True)  # noqa: E712
    policies = (await db.execute(query)).scalars().all()

    query_terms = _tokenize(q)
    docs = [_tokenize(f"{p.title} {p.title} {p.content}") for p in policies]  # title weighted 2x
    scores = _bm25_rank(query_terms, docs)
    ranked = sorted(zip(scores, policies), key=lambda x: (-x[0], x[1].policy_code))
    top = [p for score, p in ranked[:3] if score > 0]

    if not top:
        return FinanceQueryResponse(
            answer="No matching policies found for that question.",
            tools_used=["policy_search"],
            sources=["policies"],
        )
    data = [
        {"policy_code": p.policy_code, "title": p.title, "excerpt": p.content[:300]}
        for p in top
    ]
    return FinanceQueryResponse(
        answer=f"Found {len(top)} relevant policies. Most relevant: {top[0].policy_code} — {top[0].title}.",
        data=data,
        tools_used=["policy_search"],
        sources=[p.policy_code for p in top],
    )


async def _overview(db: AsyncSession) -> FinanceQueryResponse:
    inv_count = await db.scalar(select(func.count(Invoice.id))) or 0
    pending = await db.scalar(select(func.count(Approval.id)).where(Approval.status == "PENDING")) or 0
    total = await db.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0))) or 0
    return FinanceQueryResponse(
        answer=(
            f"Overview: {inv_count} invoices on record worth {_fmt(float(total))}; "
            f"{pending} pending approvals. Ask about spend, pending approvals, top vendors, "
            f"duplicates, high-risk invoices, status breakdown, or policies."
        ),
        data=[{"invoices": inv_count, "pending_approvals": pending, "total_value": float(total)}],
        tools_used=["sql_aggregation"],
        sources=["invoices", "approvals"],
    )

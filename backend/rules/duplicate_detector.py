from __future__ import annotations

"""Deterministic duplicate invoice detection.

  - Exact: same (vendor_id, invoice_number) on a different invoice -> 1.0.
  - Fuzzy: same vendor, total within ±1%, invoice date within 30 days ->
    weighted confidence from amount similarity, date proximity, and
    invoice-number similarity (difflib, deterministic).
"""

from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Invoice
from backend.rules.config import RulesConfig, get_rules_config

_W_AMOUNT = 0.40
_W_DATE = 0.30
_W_NUMBER = 0.30


def _number_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").upper(), (b or "").upper()).ratio()


async def detect_duplicates(
    db: AsyncSession,
    invoice: Invoice,
    config: RulesConfig | None = None,
) -> dict[str, Any]:
    config = config or get_rules_config()

    if invoice.vendor_id is None:
        return {"duplicate": False, "confidence": 0.0, "matched_invoice": None, "match_type": None}

    # Exact match: same vendor + same invoice number, different row
    exact_q = select(Invoice).where(
        Invoice.vendor_id == invoice.vendor_id,
        Invoice.invoice_number == invoice.invoice_number,
        Invoice.id != invoice.id,
    )
    exact = (await db.execute(exact_q)).scalars().first()
    if exact is not None:
        return {
            "duplicate": True,
            "confidence": 1.0,
            "matched_invoice": exact.invoice_number,
            "matched_invoice_id": str(exact.id),
            "match_type": "EXACT",
            "details": "Exact match on vendor and invoice number",
        }

    # Fuzzy match: same vendor, amount within ±1%, date within 30 days
    total = Decimal(str(invoice.total_amount or 0))
    amount_tolerance = total * Decimal(str(config.DUPLICATE_AMOUNT_TOLERANCE))
    window = timedelta(days=config.DUPLICATE_DATE_WINDOW_DAYS)

    fuzzy_q = select(Invoice).where(
        Invoice.vendor_id == invoice.vendor_id,
        Invoice.id != invoice.id,
        Invoice.total_amount >= float(total - amount_tolerance),
        Invoice.total_amount <= float(total + amount_tolerance),
    )
    if invoice.invoice_date is not None:
        fuzzy_q = fuzzy_q.where(
            Invoice.invoice_date >= invoice.invoice_date - window,
            Invoice.invoice_date <= invoice.invoice_date + window,
        )

    best_confidence = 0.0
    best_match: Invoice | None = None
    for candidate in (await db.execute(fuzzy_q)).scalars().all():
        cand_total = Decimal(str(candidate.total_amount or 0))
        amount_diff_ratio = float(abs(cand_total - total) / total) if total else 1.0
        amount_sim = max(0.0, 1.0 - amount_diff_ratio / config.DUPLICATE_AMOUNT_TOLERANCE)

        if invoice.invoice_date and candidate.invoice_date:
            days_apart = abs((candidate.invoice_date - invoice.invoice_date).days)
            date_sim = max(0.0, 1.0 - days_apart / config.DUPLICATE_DATE_WINDOW_DAYS)
        else:
            date_sim = 0.0

        number_sim = _number_similarity(invoice.invoice_number, candidate.invoice_number)

        confidence = round(_W_AMOUNT * amount_sim + _W_DATE * date_sim + _W_NUMBER * number_sim, 4)
        if confidence > best_confidence:
            best_confidence = confidence
            best_match = candidate

    is_duplicate = best_confidence >= config.DUPLICATE_CONFIDENCE_THRESHOLD
    return {
        "duplicate": is_duplicate,
        "confidence": best_confidence,
        "matched_invoice": best_match.invoice_number if best_match else None,
        "matched_invoice_id": str(best_match.id) if best_match else None,
        "match_type": "FUZZY" if best_match else None,
        "threshold": config.DUPLICATE_CONFIDENCE_THRESHOLD,
    }

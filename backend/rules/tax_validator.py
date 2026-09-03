from __future__ import annotations

"""Deterministic tax & arithmetic validation for invoices.

Checks (all with ₹1.00 rounding tolerance):
  1. subtotal + tax_amount == total_amount
  2. tax_amount == subtotal * GST_RATE (18%)
  3. sum(item.quantity * item.unit_price) == subtotal
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from backend.models import Invoice
from backend.rules.config import RulesConfig, get_rules_config

_CENT = Decimal("0.01")


def _dec(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(_CENT, rounding=ROUND_HALF_UP)


def validate_taxes(invoice: Invoice, config: RulesConfig | None = None) -> dict[str, Any]:
    config = config or get_rules_config()
    tolerance = Decimal(str(config.AMOUNT_TOLERANCE))
    gst_rate = Decimal(str(config.GST_RATE))

    subtotal = _dec(invoice.subtotal)
    tax_amount = _dec(invoice.tax_amount)
    total_amount = _dec(invoice.total_amount)

    errors: list[str] = []

    # 1. Arithmetic: subtotal + tax == total
    computed_total = subtotal + tax_amount
    totals_match = abs(computed_total - total_amount) <= tolerance
    if not totals_match:
        errors.append(
            f"Total mismatch: subtotal ({subtotal}) + tax ({tax_amount}) = {computed_total}, "
            f"but total is {total_amount}"
        )

    # 2. GST rate check: tax == subtotal * 18%
    expected_tax = (subtotal * gst_rate).quantize(_CENT, rounding=ROUND_HALF_UP)
    actual_rate_pct = float((tax_amount / subtotal * 100).quantize(_CENT)) if subtotal else 0.0
    gst_correct = abs(expected_tax - tax_amount) <= tolerance
    if not gst_correct:
        errors.append(
            f"Tax amount mismatch: expected {float(gst_rate) * 100:.2f}% "
            f"({expected_tax}), got {actual_rate_pct:.2f}% ({tax_amount})"
        )

    # 3. Line items sum == subtotal (only when items exist)
    items = list(invoice.items or [])
    items_sum = sum((_dec(i.unit_price) * i.quantity for i in items), Decimal("0"))
    line_items_match = True
    if items:
        line_items_match = abs(items_sum - subtotal) <= tolerance
        if not line_items_match:
            errors.append(
                f"Line items sum ({items_sum}) does not match subtotal ({subtotal})"
            )

    return {
        "valid": not errors,
        "totals_match": totals_match,
        "gst_correct": gst_correct,
        "line_items_match": line_items_match,
        "expected_tax": float(expected_tax),
        "actual_tax": float(tax_amount),
        "expected_gst_rate_pct": float(gst_rate) * 100,
        "actual_gst_rate_pct": actual_rate_pct,
        "line_items_sum": float(items_sum),
        "subtotal": float(subtotal),
        "total_amount": float(total_amount),
        "errors": errors,
    }

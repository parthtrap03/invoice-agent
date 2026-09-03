from __future__ import annotations

"""Deterministic 2-way matching between an Invoice and its Purchase Order.

Checks:
  - PO exists and is ACTIVE
  - Invoice vendor matches PO vendor
  - Line item descriptions & quantities match
  - Amount variance: ((invoice_subtotal - po_total) / po_total) * 100,
    flagged when it exceeds the configured tolerance (2%).
"""

from decimal import Decimal
from typing import Any

from backend.models import Invoice, PurchaseOrder
from backend.rules.config import RulesConfig, get_rules_config


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def match_purchase_order(
    invoice: Invoice,
    po: PurchaseOrder | None,
    config: RulesConfig | None = None,
) -> dict[str, Any]:
    config = config or get_rules_config()
    tolerance_pct = config.PO_VARIANCE_TOLERANCE * 100

    issues: list[str] = []

    if po is None:
        return {
            "matched": False,
            "po_found": False,
            "po_number": None,
            "issues": ["No matching PO found"],
            "variance_pct": None,
            "variance_acceptable": None,
            "threshold": tolerance_pct,
        }

    po_active = po.status == "ACTIVE"
    if not po_active:
        issues.append(f"PO {po.po_number} is not ACTIVE (status: {po.status})")

    vendor_match = invoice.vendor_id == po.vendor_id
    if not vendor_match:
        issues.append(f"Invoice vendor does not match PO {po.po_number} vendor")

    # Line item description & quantity check
    po_items = {(_normalize(i.description)): i for i in (po.items or [])}
    line_item_issues: list[str] = []
    for item in invoice.items or []:
        key = _normalize(item.description)
        po_item = po_items.get(key)
        if po_item is None:
            line_item_issues.append(f"Line item '{item.description}' not found on PO")
        elif po_item.quantity != item.quantity:
            line_item_issues.append(
                f"Quantity mismatch for '{item.description}': invoice {item.quantity} vs PO {po_item.quantity}"
            )
    line_items_match = not line_item_issues
    issues.extend(line_item_issues)

    # Amount variance (invoice pre-tax amount vs PO amount)
    po_total = Decimal(str(po.total_amount))
    invoice_amount = Decimal(str(invoice.subtotal))
    variance_pct = float((invoice_amount - po_total) / po_total * 100) if po_total else 0.0
    variance_pct = round(variance_pct, 2)
    variance_acceptable = variance_pct <= tolerance_pct
    if not variance_acceptable:
        issues.append(
            f"PO variance ({variance_pct:.2f}%) exceeds tolerance ({tolerance_pct:.2f}%)"
        )

    return {
        "matched": po_active and vendor_match and line_items_match and variance_acceptable,
        "po_found": True,
        "po_number": po.po_number,
        "po_status": po.status,
        "po_active": po_active,
        "vendor_match": vendor_match,
        "line_items_match": line_items_match,
        "po_amount": float(po_total),
        "invoice_amount": float(invoice_amount),
        "variance_pct": variance_pct,
        "variance_acceptable": variance_acceptable,
        "threshold": tolerance_pct,
        "issues": issues,
    }

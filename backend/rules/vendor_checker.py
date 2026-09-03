from __future__ import annotations

"""Deterministic vendor compliance & risk checks.

  - Vendor must exist, be `is_active`, and have status == "ACTIVE".
  - Vendor risk_score (0–100) above 70 flags the vendor as HIGH risk.
"""

from typing import Any

from backend.models import Vendor
from backend.rules.config import RulesConfig, get_rules_config


def check_vendor(vendor: Vendor | None, config: RulesConfig | None = None) -> dict[str, Any]:
    config = config or get_rules_config()

    if vendor is None:
        return {
            "vendor_found": False,
            "active": False,
            "high_risk": False,
            "risk_level": "UNKNOWN",
            "issues": ["No vendor linked to invoice"],
        }

    issues: list[str] = []
    active = bool(vendor.is_active) and vendor.status == "ACTIVE"
    if not active:
        issues.append(f"Vendor '{vendor.name}' is inactive (status: {vendor.status})")

    risk_score = float(vendor.risk_score or 0)
    high_risk = risk_score > config.VENDOR_HIGH_RISK_THRESHOLD
    if high_risk:
        issues.append(
            f"Vendor '{vendor.name}' is HIGH risk "
            f"(score {risk_score:.0f} > {config.VENDOR_HIGH_RISK_THRESHOLD:.0f})"
        )

    if high_risk:
        risk_level = "HIGH"
    elif risk_score > 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "vendor_found": True,
        "vendor": vendor.name,
        "vendor_code": vendor.vendor_code,
        "status": vendor.status,
        "active": active,
        "risk_score": risk_score,
        "high_risk": high_risk,
        "risk_level": risk_level,
        "issues": issues,
    }

from __future__ import annotations

"""Deterministic cumulative risk scoring and AI decision derivation.

Weights (max 100): PO variance 30, approval threshold 25, duplicate 35,
inactive/high-risk vendor 30, tax discrepancy 15. Hard-fail conditions
(duplicate, inactive vendor) floor the score at HARD_FAIL_RISK_FLOOR.

Bands: LOW 0–30, MEDIUM 31–60, HIGH 61–100.

Decision:
  - REJECT:          duplicate detected OR vendor inactive OR risk >= 61
  - REVIEW_REQUIRED: risk 31–60 OR variance > tolerance OR total > ₹10L
                     OR any other violation (e.g. tax discrepancy)
  - AUTO_APPROVE:    risk <= 30 and no violations and total <= ₹10L
"""

from typing import Any

from backend.rules.config import RulesConfig, get_rules_config


def score_risk(
    total_amount: float,
    validation_result: dict[str, Any],
    po_match_result: dict[str, Any],
    duplicate_result: dict[str, Any],
    vendor_result: dict[str, Any],
    config: RulesConfig | None = None,
) -> dict[str, Any]:
    config = config or get_rules_config()
    weights = config.weights

    score = 0
    reasons: list[str] = []
    violations: list[str] = []

    # PO variance
    variance_pct = po_match_result.get("variance_pct")
    variance_exceeded = po_match_result.get("variance_acceptable") is False
    if variance_exceeded:
        score += weights.PO_VARIANCE
        reasons.append(
            f"PO variance ({variance_pct:.2f}%) exceeds tolerance "
            f"({config.PO_VARIANCE_TOLERANCE * 100:.2f}%)"
        )
        violations.append("PO_VARIANCE")

    # Approval threshold
    above_threshold = float(total_amount or 0) > config.APPROVAL_THRESHOLD
    if above_threshold:
        score += weights.APPROVAL_THRESHOLD
        reasons.append(
            f"Invoice amount ₹{float(total_amount):,.2f} exceeds approval "
            f"threshold ₹{config.APPROVAL_THRESHOLD:,.0f}"
        )
        violations.append("APPROVAL_THRESHOLD")

    # Duplicate
    is_duplicate = bool(duplicate_result.get("duplicate"))
    if is_duplicate:
        score += weights.DUPLICATE
        matched = duplicate_result.get("matched_invoice")
        confidence = duplicate_result.get("confidence", 0.0)
        reasons.append(
            f"Duplicate invoice detected ({confidence * 100:.0f}% confidence"
            + (f", matches {matched})" if matched else ")")
        )
        violations.append("DUPLICATE")

    # Vendor inactive / high risk
    vendor_inactive = vendor_result.get("vendor_found", False) and not vendor_result.get("active", False)
    vendor_high_risk = bool(vendor_result.get("high_risk"))
    if vendor_inactive or vendor_high_risk:
        score += weights.VENDOR_RISK
        reasons.extend(vendor_result.get("issues", []))
        violations.append("VENDOR_RISK")

    # Tax discrepancy
    tax_invalid = not validation_result.get("valid", True)
    if tax_invalid:
        score += weights.TAX_DISCREPANCY
        reasons.extend(validation_result.get("errors", []))
        violations.append("TAX_DISCREPANCY")

    # Hard-fail conditions floor the score
    hard_fail = is_duplicate or vendor_inactive
    if hard_fail:
        score = max(score, config.HARD_FAIL_RISK_FLOOR)
    score = min(score, 100)

    # Band
    if score <= config.RISK_LOW_MAX:
        risk_level = "LOW"
    elif score <= config.RISK_MEDIUM_MAX:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    # Decision
    if hard_fail or score > config.RISK_MEDIUM_MAX:
        decision = "REJECT"
    elif violations or score > config.RISK_LOW_MAX:
        decision = "REVIEW_REQUIRED"
    else:
        decision = "AUTO_APPROVE"

    return {
        "decision": decision,
        "risk_score": score,
        "risk_level": risk_level,
        "reasons": reasons,
        "violations": violations,
        "hard_fail": hard_fail,
        "above_approval_threshold": above_threshold,
    }

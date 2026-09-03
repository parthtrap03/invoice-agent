from __future__ import annotations

"""Centralized, deterministic configuration for the financial rules engine.

Thresholds come from application settings (env-overridable); risk weights and
band boundaries are fixed business constants.
"""

from dataclasses import dataclass, field
from functools import lru_cache

from backend.config import get_settings


@dataclass(frozen=True)
class RiskWeights:
    """Points each violation contributes to the cumulative risk score (max 100)."""

    PO_VARIANCE: int = 30
    APPROVAL_THRESHOLD: int = 25
    DUPLICATE: int = 35
    VENDOR_RISK: int = 30
    TAX_DISCREPANCY: int = 15


@dataclass(frozen=True)
class RulesConfig:
    APPROVAL_THRESHOLD: float = 1000000.0        # ₹10 Lakhs
    PO_VARIANCE_TOLERANCE: float = 0.02          # 2.0%
    GST_RATE: float = 0.18                       # 18%
    DUPLICATE_CONFIDENCE_THRESHOLD: float = 0.85  # 85%

    AMOUNT_TOLERANCE: float = 1.00               # ₹1.00 rounding tolerance
    VENDOR_HIGH_RISK_THRESHOLD: float = 70.0     # vendor risk_score > 70 => HIGH
    DUPLICATE_AMOUNT_TOLERANCE: float = 0.01     # ±1% for fuzzy amount match
    DUPLICATE_DATE_WINDOW_DAYS: int = 30         # fuzzy date proximity window
    HARD_FAIL_RISK_FLOOR: int = 85               # min risk when a hard-fail rule fires

    RISK_LOW_MAX: int = 30                       # LOW: 0–30
    RISK_MEDIUM_MAX: int = 60                    # MEDIUM: 31–60; HIGH: 61–100

    weights: RiskWeights = field(default_factory=RiskWeights)


@lru_cache
def get_rules_config() -> RulesConfig:
    settings = get_settings()
    return RulesConfig(
        APPROVAL_THRESHOLD=settings.APPROVAL_THRESHOLD,
        PO_VARIANCE_TOLERANCE=settings.PO_VARIANCE_TOLERANCE,
        GST_RATE=settings.GST_RATE,
        DUPLICATE_CONFIDENCE_THRESHOLD=settings.DUPLICATE_CONFIDENCE_THRESHOLD,
    )

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Policy, PurchaseOrder, PurchaseOrderItem, Vendor

"""Demo seed data.

Deliberately small and deterministic: four vendors (one inactive), two active
purchase orders that the demo invoices in uploads/demo/ match against, and the
company policy library exposed at /api/policies.

Invoices are NOT seeded - they are meant to be uploaded through the app so the
extraction and rules pipeline runs for real.
"""


async def seed_database(db: AsyncSession) -> None:
    """Populate the database with demo master data. Idempotent."""
    existing = await db.scalar(select(func.count()).select_from(Vendor))
    if existing:
        return

    vendors = _build_vendors()
    db.add_all(vendors)
    _add_purchase_orders(db, vendors)
    await _seed_policies(db)
    await db.commit()


def _build_vendors() -> list[Vendor]:
    def vendor(code: str, name: str, tax_id: str, risk: float, active: bool = True) -> Vendor:
        return Vendor(
            id=uuid.uuid4(),
            vendor_code=code,
            name=name,
            category="IT Services",
            status="ACTIVE" if active else "INACTIVE",
            contact_email=f"billing@{code.lower()}.in",
            tax_id=tax_id,
            risk_score=Decimal(str(risk)),
            is_active=active,
        )

    return [
        vendor("VEND-101", "Zenith IT Solutions", "27ZENITH9001Z1", 10),
        vendor("VEND-102", "ABC Cloud Services", "27ABCCLOUD02Z2", 15),
        vendor("VEND-103", "Deluxe Office Supplies", "27DELUXE003Z3", 20),
        vendor("VEND-104", "Phantom Traders", "27PHANTOM04Z4", 65, active=False),
    ]


def _add_purchase_orders(db: AsyncSession, vendors: list[Vendor]) -> None:
    by_code = {v.vendor_code: v for v in vendors}

    def add_po(number: str, vendor: Vendor, total: str, desc: str, qty: int, unit: str) -> None:
        po = PurchaseOrder(
            id=uuid.uuid4(),
            po_number=number,
            vendor_id=vendor.id,
            total_amount=Decimal(total),
            currency="INR",
            status="ACTIVE",
            issue_date=date.today() - timedelta(days=20),
            department="IT",
        )
        db.add(po)
        db.add(PurchaseOrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            description=desc,
            quantity=qty,
            unit_price=Decimal(unit),
            total_price=Decimal(unit) * qty,
        ))

    # Matches uploads/demo/01 exactly -> AUTO_APPROVE
    add_po("PO-5001", by_code["VEND-101"], "400000.00", "Software Development Services", 4, "100000.00")
    # uploads/demo/02 bills Rs.18,40,000 against this -> 2.22% variance -> REVIEW
    add_po("PO-99182", by_code["VEND-102"], "1800000.00", "Cloud Infrastructure Services", 12, "150000.00")


async def _seed_policies(db: AsyncSession) -> None:
    policy_data = [
        ("POL-FIN-001", "Invoice Approval Threshold", "Finance",
         "All invoices with a total amount exceeding \u20b910,00,000 (ten lakh) require manual approval from a finance manager or above. Invoices below this threshold may be auto-approved if all other checks pass.", "3.2"),
        ("POL-FIN-002", "PO Variance Tolerance", "Procurement",
         "Invoice amounts must not exceed the corresponding Purchase Order amount by more than 2%. Any variance above 2% requires manual review and approval.", "2.1"),
        ("POL-VEN-001", "Vendor Status Policy", "Vendor Management",
         "Invoices from vendors marked as INACTIVE in the vendor management system must be automatically rejected. Only invoices from ACTIVE vendors may proceed through the approval workflow.", "1.5"),
        ("POL-TAX-001", "GST Compliance", "Tax",
         "All service invoices must include GST at the rate of 18%. The tax amount must equal exactly 18% of the subtotal. Any deviation must be flagged for review.", "2.0"),
        ("POL-DUP-001", "Duplicate Invoice Detection", "Finance",
         "Invoices with a similarity score exceeding 85% when compared against existing invoices from the same vendor must be flagged as potential duplicates. Exact matches on invoice number must be automatically rejected.", "1.3"),
        ("POL-PAY-001", "Payment Terms Policy", "Finance",
         "Standard payment terms are NET30 unless specifically negotiated in the vendor contract. Early payment discounts may be applied only with finance manager approval.", "2.0"),
        ("POL-APP-001", "Approval Matrix", "Finance",
         "Invoices up to \u20b91,00,000: Auto-approve if all checks pass. \u20b91,00,001 to \u20b910,00,000: Team lead approval. \u20b910,00,001 to \u20b950,00,000: Finance manager approval. Above \u20b950,00,000: CFO approval.", "3.0"),
        ("POL-PRO-001", "Purchase Order Requirement", "Procurement",
         "All invoices exceeding \u20b925,000 must reference a valid Purchase Order. Invoices without a PO reference must be routed for manual review.", "2.3"),
        ("POL-VEN-002", "Vendor Risk Assessment", "Vendor Management",
         "Vendors with a risk score above 70 are classified as HIGH risk. Invoices from HIGH risk vendors require additional scrutiny and finance manager approval regardless of amount.", "1.2"),
        ("POL-FIN-003", "Invoice Age Policy", "Finance",
         "Invoices older than 90 days from the invoice date must be flagged for review. Invoices older than 180 days must be rejected unless explicitly approved by the CFO.", "1.1"),
        ("POL-PRO-002", "Procurement Guidelines", "Procurement",
         "All procurement above \u20b95,00,000 must go through the formal procurement process including RFP, vendor evaluation, and contract negotiation before a PO is issued.", "3.1"),
        ("POL-FIN-004", "Budget Compliance", "Finance",
         "Invoice approval requires verification that the associated cost center has sufficient budget allocation for the current fiscal quarter.", "2.0"),
        ("POL-SEC-001", "Data Classification", "Security",
         "All financial documents including invoices, POs, and contracts are classified as INTERNAL. Access is restricted to authorized finance and procurement personnel.", "1.0"),
        ("POL-AUD-001", "Audit Trail Requirements", "Compliance",
         "All financial transactions must maintain a complete audit trail including timestamps, user actions, system decisions, and approval records. Audit logs must be retained for 7 years.", "2.5"),
        ("POL-VEN-003", "Contract Validity", "Vendor Management",
         "Invoices can only be processed against valid, non-expired vendor contracts. If the contract has expired, the invoice must be held until contract renewal is completed.", "1.4"),
        ("POL-FIN-005", "Currency Policy", "Finance",
         "All domestic invoices must be denominated in INR. Foreign currency invoices require treasury department approval and must use the exchange rate as of the invoice date.", "1.0"),
        ("POL-TAX-002", "TDS Compliance", "Tax",
         "Tax Deducted at Source (TDS) must be applied as per applicable sections of the Income Tax Act. TDS certificates must be issued quarterly.", "2.1"),
        ("POL-PRO-003", "Vendor Onboarding", "Procurement",
         "New vendors must complete the onboarding process including KYC verification, bank account validation, and compliance certification before any POs can be issued.", "1.6"),
        ("POL-FIN-006", "Invoice Processing SLA", "Finance",
         "Standard invoices must be processed within 5 business days. High-priority invoices must be processed within 2 business days. Processing time is measured from upload to final decision.", "1.0"),
        ("POL-SEC-002", "Access Control", "Security",
         "Access to financial systems follows the principle of least privilege. Invoice viewing requires READER role. Invoice approval requires APPROVER role. System configuration requires ADMIN role.", "1.3"),
    ]

    for code, title, category, content, version in policy_data:
        p = Policy(
            id=uuid.uuid4(),
            policy_code=code,
            title=title,
            category=category,
            content=content,
            version=version,
            is_active=True,
        )
        db.add(p)

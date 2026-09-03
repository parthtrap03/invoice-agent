from __future__ import annotations

"""One-shot demo setup: clean database + generate demo invoice PDFs.

Usage:
    .\\venv\\Scripts\\python.exe setup_demo.py

What it does:
  1. Deletes finance_agent.db (fresh start)
  2. Creates tables and seeds ONLY what the demo needs:
       - 4 vendors (one inactive) with tax IDs
       - 2 ACTIVE purchase orders that match the demo invoices
       - the UNFPA policy document into the policy library, if downloaded
  3. Generates 5 realistic invoice PDFs into uploads/demo/, each crafted to
     exercise a different rules-engine outcome:
       01 -> AUTO_APPROVE      (clean, PO match, 18% GST, < Rs.10L)
       02 -> REVIEW_REQUIRED   (2.22% PO variance + > Rs.10L)
       03 -> REVIEW_REQUIRED   (5% GST instead of 18%)
       04 -> REJECT            (inactive vendor)
       05 -> REJECT            (upload TWICE - duplicate detection)

Because vendors exist afterwards, the app's startup seeder skips its random
demo data - the database stays clean for the walkthrough.
"""

import asyncio
import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

DB_FILE = "finance_agent.db"
OUT_DIR = os.path.join("uploads", "demo")
UNFPA_POLICY = os.path.join("uploads", "policies", "unfpa-accounts-payable-policy.pdf")

TODAY = date.today()
DUE = TODAY + timedelta(days=30)


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------
def make_invoice_pdf(
    path: str,
    invoice_no: str,
    vendor: str,
    gstin: str,
    po_number: str | None,
    items: list[tuple[str, int, float]],
    gst_rate: float,
    note: str,
) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    subtotal = sum(qty * price for _, qty, price in items)
    tax = round(subtotal * gst_rate, 2)
    total = round(subtotal + tax, 2)

    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 25 * mm

    def line(text: str, size: int = 11, bold: bool = False, dy: float = 7 * mm):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(20 * mm, y, text)
        y -= dy

    line("TAX INVOICE", 18, True, 12 * mm)
    line(f"Vendor: {vendor}", 12, True)
    line(f"GSTIN: {gstin}")
    line(f"Invoice No: {invoice_no}", 12, True)
    if po_number:
        line(f"PO Number: {po_number}")
    line(f"Invoice Date: {TODAY.isoformat()}")
    line(f"Due Date: {DUE.isoformat()}")
    line("Payment Terms: NET 30")
    y -= 4 * mm

    line("Description                              Qty      Unit Price          Amount", 10, True, 6 * mm)
    c.line(20 * mm, y + 4 * mm, w - 20 * mm, y + 4 * mm)
    for desc, qty, price in items:
        line(f"{desc:<38}   {qty:>3}      {qty and price:>10.2f}      {qty * price:>12.2f}", 10, False, 6 * mm)
    c.line(20 * mm, y + 4 * mm, w - 20 * mm, y + 4 * mm)
    y -= 4 * mm

    line(f"Subtotal: Rs. {subtotal:,.2f}", 12)
    line(f"GST ({gst_rate * 100:.0f}%): Rs. {tax:,.2f}", 12)
    line(f"Grand Total: Rs. {total:,.2f}", 13, True)
    y -= 6 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(20 * mm, y, f"[demo scenario: {note}]")
    c.save()


# ---------------------------------------------------------------------------
# Database seed (vendors + POs only)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
async def main() -> None:
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"[1/4] Deleted {DB_FILE}")
    else:
        print(f"[1/4] No existing {DB_FILE}")

    from backend.database import async_sessionmaker_factory, init_db
    from backend.seed import seed_database

    await init_db()
    async with async_sessionmaker_factory() as db:
        await seed_database(db)
    print("[2/4] Seeded 4 vendors + 2 purchase orders + 20 policies")

    if os.path.exists(UNFPA_POLICY):
        from backend.services.policy_service import ingest_policy_document

        async with async_sessionmaker_factory() as db:
            created = await ingest_policy_document(db, UNFPA_POLICY, category="Accounts Payable")
        print(f"[3/4] Ingested UNFPA policy document ({len(created)} sections) into the policy library")
    else:
        print("[3/4] UNFPA policy PDF not found - skipped")

    os.makedirs(OUT_DIR, exist_ok=True)
    make_invoice_pdf(
        os.path.join(OUT_DIR, "01-clean-auto-approve.pdf"),
        "INV-2001", "Zenith IT Solutions", "27ZENITH9001Z1", "PO-5001",
        [("Software Development Services", 4, 100000.00)], 0.18,
        "clean invoice, matches PO-5001 exactly -> AUTO_APPROVE",
    )
    make_invoice_pdf(
        os.path.join(OUT_DIR, "02-po-variance-review.pdf"),
        "INV-88231", "ABC Cloud Services", "27ABCCLOUD02Z2", "PO-99182",
        [("Cloud Infrastructure Services", 12, 153333.33)], 0.18,
        "2.22% over PO-99182 + above Rs.10L threshold -> REVIEW_REQUIRED",
    )
    make_invoice_pdf(
        os.path.join(OUT_DIR, "03-wrong-gst-review.pdf"),
        "INV-3003", "Deluxe Office Supplies", "27DELUXE003Z3", None,
        [("Office Furniture Set", 2, 100000.00)], 0.05,
        "5% GST instead of 18% -> REVIEW_REQUIRED",
    )
    make_invoice_pdf(
        os.path.join(OUT_DIR, "04-inactive-vendor-reject.pdf"),
        "INV-4004", "Phantom Traders", "27PHANTOM04Z4", None,
        [("Consulting Retainer", 1, 150000.00)], 0.18,
        "vendor is INACTIVE -> REJECT",
    )
    make_invoice_pdf(
        os.path.join(OUT_DIR, "05-duplicate-reject.pdf"),
        "INV-5005", "Zenith IT Solutions", "27ZENITH9001Z1", None,
        [("Annual Support Contract", 1, 250000.00)], 0.18,
        "upload this file TWICE - second one -> REJECT (duplicate)",
    )
    print(f"[4/4] Generated 5 demo invoice PDFs in {OUT_DIR}/")
    print()
    print("Demo walkthrough (upload each via the frontend Upload page, then Process):")
    print("  01-clean-auto-approve.pdf      -> AUTO_APPROVE  (risk LOW)")
    print("  02-po-variance-review.pdf      -> REVIEW_REQUIRED (variance 2.22% + > Rs.10L)")
    print("  03-wrong-gst-review.pdf        -> REVIEW_REQUIRED (tax mismatch)")
    print("  04-inactive-vendor-reject.pdf  -> REJECT (inactive vendor)")
    print("  05-duplicate-reject.pdf        -> process once, upload AGAIN, process -> REJECT (duplicate)")


if __name__ == "__main__":
    asyncio.run(main())

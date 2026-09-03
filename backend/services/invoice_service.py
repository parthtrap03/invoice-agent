from __future__ import annotations
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import Invoice, InvoiceItem, PurchaseOrder, Vendor
from backend.schemas.extraction import ExtractedInvoice

async def list_invoices(db: AsyncSession, page: int = 1, page_size: int = 20, status: str | None = None, vendor_id: UUID | None = None) -> tuple[list[Invoice], int]:
    query = select(Invoice).options(selectinload(Invoice.vendor))
    
    if status:
        query = query.where(Invoice.status == status)
    if vendor_id:
        query = query.where(Invoice.vendor_id == vendor_id)
        
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0
    
    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    invoices = list(result.scalars().all())
    
    return invoices, total_count

async def get_invoice(db: AsyncSession, invoice_id: UUID) -> Invoice | None:
    query = select(Invoice).where(Invoice.id == invoice_id).options(
        selectinload(Invoice.vendor),
        selectinload(Invoice.purchase_order),
        selectinload(Invoice.items)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_invoice_from_upload(db: AsyncSession, filename: str, file_key: str | None = None) -> Invoice:
    from datetime import date
    from decimal import Decimal
    invoice = Invoice(
        invoice_number=f"UPLOAD-{filename}",
        invoice_date=date.today(),
        payment_terms="NET30",
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("0"),
        status="UPLOADED",
        source_file_key=file_key,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice

async def apply_extraction(db: AsyncSession, invoice: Invoice, extracted: ExtractedInvoice) -> Invoice:
    """Populate an uploaded invoice from extraction output.

    Resolves the vendor (by name or tax id) and PO (by number), fills the
    financial fields, replaces line items, and stores the structured
    extraction payload in `extracted_data`.
    """
    from decimal import Decimal

    if extracted.invoice_number:
        invoice.invoice_number = await _unique_invoice_number(db, extracted.invoice_number, invoice.id)

    vendor = await _resolve_vendor(db, extracted)
    if vendor is not None:
        invoice.vendor_id = vendor.id

    if extracted.po_number:
        po = (
            await db.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == extracted.po_number))
        ).scalar_one_or_none()
        if po is not None:
            invoice.po_id = po.id

    if extracted.invoice_date:
        invoice.invoice_date = extracted.invoice_date
    invoice.due_date = extracted.due_date or invoice.due_date
    invoice.payment_terms = extracted.payment_terms or invoice.payment_terms
    invoice.currency = extracted.currency or invoice.currency
    invoice.subtotal = Decimal(str(extracted.subtotal or 0))
    invoice.tax_amount = Decimal(str(extracted.tax_amount or 0))
    invoice.total_amount = Decimal(str(extracted.total_amount or 0))

    payload = extracted.model_dump(mode="json", exclude={"raw_text"})
    payload["vendor_resolved"] = vendor.name if vendor else None
    invoice.extracted_data = payload
    invoice.status = "EXTRACTED"

    # Replace any existing line items with the extracted ones
    existing_items = (
        await db.execute(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id))
    ).scalars().all()
    for item in existing_items:
        await db.delete(item)
    for li in extracted.line_items:
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                description=li.description,
                quantity=li.quantity,
                unit_price=Decimal(str(li.unit_price)),
                total_price=Decimal(str(li.total_price)),
            )
        )

    await db.commit()
    await db.refresh(invoice)
    return invoice


async def _resolve_vendor(db: AsyncSession, extracted: ExtractedInvoice) -> Vendor | None:
    if extracted.vendor_name:
        vendor = (
            await db.execute(select(Vendor).where(func.lower(Vendor.name) == extracted.vendor_name.lower()))
        ).scalar_one_or_none()
        if vendor is not None:
            return vendor
    if extracted.vendor_tax_id:
        return (
            await db.execute(select(Vendor).where(Vendor.tax_id == extracted.vendor_tax_id))
        ).scalar_one_or_none()
    return None


async def _unique_invoice_number(db: AsyncSession, number: str, own_id: UUID) -> str:
    """invoice_number is globally unique; suffix re-uploads so ingestion never
    crashes — the duplicate detector still flags them via fuzzy matching."""
    candidate = number
    suffix = 1
    while True:
        clash = (
            await db.execute(
                select(Invoice.id).where(Invoice.invoice_number == candidate, Invoice.id != own_id)
            )
        ).scalar_one_or_none()
        if clash is None:
            return candidate
        suffix += 1
        candidate = f"{number}-{suffix}"


async def update_invoice(db: AsyncSession, invoice_id: UUID, **kwargs) -> Invoice | None:
    invoice = await get_invoice(db, invoice_id)
    if invoice:
        for key, value in kwargs.items():
            setattr(invoice, key, value)
        await db.commit()
        await db.refresh(invoice)
    return invoice

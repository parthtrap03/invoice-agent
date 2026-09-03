from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import math
import os
import tempfile

from backend.database import get_db
from backend.schemas import PaginatedResponse, InvoiceListResponse, InvoiceDetailResponse, InvoiceUploadResponse, MessageResponse
from backend.models import Audit
from backend.services import file_storage
from backend.services.invoice_service import list_invoices, get_invoice, create_invoice_from_upload, apply_extraction
from backend.services.extraction_service import get_extraction_service, ExtractionError
from backend.services.orchestrator import InvoiceProcessingOrchestrator

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

@router.get("/", response_model=PaginatedResponse[InvoiceListResponse])
async def get_invoices(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    vendor_id: UUID | None = None,
    db: AsyncSession = Depends(get_db)
):
    invoices, total_count = await list_invoices(db, page=page, page_size=page_size, status=status, vendor_id=vendor_id)
    total_pages = math.ceil(total_count / page_size)
    
    items = []
    for inv in invoices:
        items.append(InvoiceListResponse(
            id=inv.id,
            invoice_number=inv.invoice_number,
            vendor_name=inv.vendor.name if inv.vendor else None,
            total_amount=inv.total_amount,
            currency=inv.currency,
            status=inv.status,
            risk_level=inv.risk_level,
            risk_score=inv.risk_score,
            ai_decision=inv.ai_decision,
            invoice_date=inv.invoice_date,
            created_at=inv.created_at
        ))
        
    return PaginatedResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
async def get_invoice_detail(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    inv = await get_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    return InvoiceDetailResponse(
        id=inv.id,
        invoice_number=inv.invoice_number,
        vendor_id=inv.vendor_id,
        po_id=inv.po_id,
        subtotal=inv.subtotal,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        currency=inv.currency,
        invoice_date=inv.invoice_date,
        due_date=inv.due_date,
        payment_terms=inv.payment_terms,
        status=inv.status,
        risk_level=inv.risk_level,
        risk_score=inv.risk_score,
        ai_decision=inv.ai_decision,
        ai_confidence=inv.ai_confidence,
        extracted_data=inv.extracted_data,
        validation_result=inv.validation_result,
        po_match_result=inv.po_match_result,
        duplicate_result=inv.duplicate_result,
        policy_result=inv.policy_result,
        vendor_risk_result=inv.vendor_risk_result,
        decision_result=inv.decision_result,
        source_file_key=inv.source_file_key,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        items=inv.items,
        vendor_name=inv.vendor.name if inv.vendor else None,
        po_number=inv.purchase_order.po_number if inv.purchase_order else None
    )

@router.post("/upload", response_model=InvoiceUploadResponse, status_code=201)
async def upload_invoice(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    # The original document is stored IN the database (stored_files table) -
    # no dependency on the server's local filesystem, deploy-safe.
    content = await file.read()
    try:
        stored = await file_storage.save_file(
            db, file.filename or "upload", content, file.content_type
        )
    except file_storage.FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    invoice = await create_invoice_from_upload(
        db, filename=stored.filename, file_key=file_storage.file_key(stored)
    )

    # Phase 2: parse the document and populate structured data + line items
    temp_path = None
    try:
        temp_path = await file_storage.materialize(db, invoice.source_file_key)
        extracted = await get_extraction_service().extract(temp_path)
        invoice = await apply_extraction(db, invoice, extracted)
    except ExtractionError:
        invoice.status = "EXTRACTION_FAILED"
        await db.commit()
        await db.refresh(invoice)
    finally:
        if temp_path and temp_path.startswith(tempfile.gettempdir()):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    db.add(Audit(
        user_name="api",
        invoice_id=invoice.id,
        action="INVOICE_UPLOADED",
        entity_type="Invoice",
        entity_id=invoice.id,
        details={"filename": stored.filename, "status": invoice.status, "stored_file_id": str(stored.id)},
    ))
    await db.commit()

    return InvoiceUploadResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        source_file_key=invoice.source_file_key,
        created_at=invoice.created_at
    )

@router.post("/{invoice_id}/process")
async def process_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    inv = await get_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Full traced pipeline: extraction (if pending) + deterministic rules engine
    try:
        run, result = await InvoiceProcessingOrchestrator().process_invoice(db, invoice_id)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {exc}")

    payload = result.model_dump(mode="json")
    payload["agent_run_id"] = str(run.id)
    return payload

@router.get("/{invoice_id}/file")
async def download_invoice_file(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    """Serve the original uploaded document straight from the database."""
    inv = await get_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.source_file_key:
        raise HTTPException(status_code=404, detail="No source document for this invoice")

    stored = await file_storage.get_file(db, inv.source_file_key)
    if stored is None:
        raise HTTPException(status_code=404, detail="Source document not found in storage")

    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'inline; filename="{stored.filename}"'},
    )

@router.get("/{invoice_id}/analysis")
async def get_invoice_analysis(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    inv = await get_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    return {
        "extracted_data": inv.extracted_data,
        "validation_result": inv.validation_result,
        "po_match_result": inv.po_match_result,
        "duplicate_result": inv.duplicate_result,
        "policy_result": inv.policy_result,
        "vendor_risk_result": inv.vendor_risk_result,
        "decision_result": inv.decision_result
    }

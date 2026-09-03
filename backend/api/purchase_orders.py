from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import math

from backend.database import get_db
from backend.schemas import PaginatedResponse, PurchaseOrderResponse
from backend.services.po_service import list_purchase_orders, get_purchase_order

router = APIRouter(prefix="/api/purchase-orders", tags=["Purchase Orders"])

@router.get("/", response_model=PaginatedResponse[PurchaseOrderResponse])
async def get_all_pos(
    page: int = 1,
    page_size: int = 20,
    vendor_id: UUID | None = None,
    db: AsyncSession = Depends(get_db)
):
    pos, total_count = await list_purchase_orders(db, page=page, page_size=page_size, vendor_id=vendor_id)
    total_pages = math.ceil(total_count / page_size)
    
    items = []
    for po in pos:
        response = PurchaseOrderResponse.model_validate(po)
        response.vendor_name = po.vendor.name if po.vendor else None
        items.append(response)
        
    return PaginatedResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/{po_id}", response_model=PurchaseOrderResponse)
async def get_po_by_id(po_id: UUID, db: AsyncSession = Depends(get_db)):
    po = await get_purchase_order(db, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    response = PurchaseOrderResponse.model_validate(po)
    response.vendor_name = po.vendor.name if po.vendor else None
    return response

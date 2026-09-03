from __future__ import annotations
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import PurchaseOrder

async def list_purchase_orders(db: AsyncSession, page: int = 1, page_size: int = 20, vendor_id: UUID | None = None) -> tuple[list[PurchaseOrder], int]:
    query = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    )
    
    if vendor_id:
        query = query.where(PurchaseOrder.vendor_id == vendor_id)
        
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    pos = list(result.scalars().all())
    
    return pos, total_count

async def get_purchase_order(db: AsyncSession, po_id: UUID) -> PurchaseOrder | None:
    query = select(PurchaseOrder).where(PurchaseOrder.id == po_id).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_po_by_number(db: AsyncSession, po_number: str) -> PurchaseOrder | None:
    query = select(PurchaseOrder).where(PurchaseOrder.po_number == po_number).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()

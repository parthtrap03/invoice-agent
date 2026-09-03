from __future__ import annotations
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import Vendor

async def list_vendors(db: AsyncSession, page: int = 1, page_size: int = 20, is_active: bool | None = None) -> tuple[list[Vendor], int]:
    query = select(Vendor)
    
    if is_active is not None:
        query = query.where(Vendor.is_active == is_active)
        
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    vendors = list(result.scalars().all())
    
    return vendors, total_count

async def get_vendor(db: AsyncSession, vendor_id: UUID) -> Vendor | None:
    query = select(Vendor).where(Vendor.id == vendor_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_vendor_by_code(db: AsyncSession, vendor_code: str) -> Vendor | None:
    query = select(Vendor).where(Vendor.vendor_code == vendor_code)
    result = await db.execute(query)
    return result.scalar_one_or_none()

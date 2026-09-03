from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import math

from backend.database import get_db
from backend.schemas import PaginatedResponse, VendorResponse
from backend.services.vendor_service import list_vendors, get_vendor

router = APIRouter(prefix="/api/vendors", tags=["Vendors"])

@router.get("/", response_model=PaginatedResponse[VendorResponse])
async def get_all_vendors(
    page: int = 1,
    page_size: int = 20,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db)
):
    vendors, total_count = await list_vendors(db, page=page, page_size=page_size, is_active=is_active)
    total_pages = math.ceil(total_count / page_size)
    
    return PaginatedResponse(
        items=vendors,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor_by_id(vendor_id: UUID, db: AsyncSession = Depends(get_db)):
    vendor = await get_vendor(db, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor

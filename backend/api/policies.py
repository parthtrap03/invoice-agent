from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import os

from backend.database import get_db
from backend.models import Audit, Policy
from backend.services import file_storage
from backend.services.extraction_service import ExtractionError
from backend.services.policy_service import ingest_policy_document

router = APIRouter(prefix="/api/policies", tags=["Policies"])


def _to_dict(p: Policy) -> dict:
    return {
        "id": str(p.id),
        "policy_code": p.policy_code,
        "title": p.title,
        "category": p.category,
        "content": p.content,
        "version": p.version,
        "is_active": p.is_active,
    }


@router.get("/")
async def list_policies(
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Policy).where(Policy.is_active == True).order_by(Policy.policy_code)  # noqa: E712
    if category:
        query = query.where(Policy.category == category)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Policy.content).like(pattern) | func.lower(Policy.title).like(pattern)
        )
    policies = (await db.execute(query)).scalars().all()
    return [_to_dict(p) for p in policies]


@router.post("/upload", status_code=201)
async def upload_policy_document(
    file: UploadFile = File(...),
    category: str = "Ingested Document",
    db: AsyncSession = Depends(get_db),
):
    """Ingest a real policy document (PDF) into the policies table.
    The original PDF is kept in the database (stored_files) as well."""
    content = await file.read()
    try:
        stored = await file_storage.save_file(db, file.filename or "policy.pdf", content, file.content_type)
    except file_storage.FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    temp_path = await file_storage.materialize(db, file_storage.file_key(stored))
    try:
        created = await ingest_policy_document(db, temp_path, category=category, source_name=stored.filename)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    db.add(Audit(
        user_name="api",
        action="POLICY_DOCUMENT_INGESTED",
        entity_type="Policy",
        details={"filename": file.filename, "sections": len(created)},
    ))
    await db.commit()

    return {
        "filename": file.filename,
        "sections_created": len(created),
        "policies": [_to_dict(p) for p in created],
    }

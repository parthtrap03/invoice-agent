from __future__ import annotations

"""Database-backed file storage.

Uploaded documents live in the `stored_files` table (BLOB), referenced from
invoices as `db://<uuid>` in `source_file_key`. One database now carries data
AND source documents - deploy-safe on ephemeral filesystems (Docker, Railway,
Render) and backed up together.

Extraction libraries (pdfplumber, RapidOCR) need a real file path, so
`materialize` writes the bytes to a session temp file on demand.
"""

import os
import re
import tempfile
import uuid as uuid_module
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import StoredFile

DB_KEY_PREFIX = "db://"
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB - plenty for invoice PDFs/scans

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class FileTooLargeError(Exception):
    pass


def sanitize_filename(filename: str) -> str:
    """Strip any path components and unsafe characters from a client-supplied
    filename (blocks path traversal like '..\\..\\evil.py')."""
    base = os.path.basename(filename.replace("\\", "/")) or "upload"
    return _SAFE_CHARS.sub("_", base)[:120]


async def save_file(db: AsyncSession, filename: str, data: bytes, content_type: str | None = None) -> StoredFile:
    if len(data) > MAX_FILE_SIZE:
        raise FileTooLargeError(f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit")
    stored = StoredFile(
        filename=sanitize_filename(filename),
        content_type=content_type or "application/octet-stream",
        size=len(data),
        data=data,
    )
    db.add(stored)
    await db.flush()
    return stored


def file_key(stored: StoredFile) -> str:
    return f"{DB_KEY_PREFIX}{stored.id}"


async def get_file(db: AsyncSession, key: str) -> StoredFile | None:
    if not key.startswith(DB_KEY_PREFIX):
        return None
    try:
        file_id = UUID(key[len(DB_KEY_PREFIX):])
    except ValueError:
        return None
    return (
        await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    ).scalar_one_or_none()


async def materialize(db: AsyncSession, source_file_key: str) -> str | None:
    """Return a local filesystem path for a stored document.

    - `db://<id>` keys: write the DB bytes to a temp file (extension kept so
      extraction adapters route correctly) and return its path.
    - legacy local paths (pre-DB-storage rows): returned as-is when they exist.
    """
    if not source_file_key:
        return None

    if source_file_key.startswith(DB_KEY_PREFIX):
        stored = await get_file(db, source_file_key)
        if stored is None:
            return None
        ext = os.path.splitext(stored.filename)[1] or ".bin"
        path = os.path.join(tempfile.gettempdir(), f"invoice-{uuid_module.uuid4().hex}{ext}")
        with open(path, "wb") as f:
            f.write(stored.data)
        return path

    return source_file_key if os.path.exists(source_file_key) else None

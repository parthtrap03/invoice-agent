from __future__ import annotations

"""Tests for database-backed file storage (deploy-safe uploads)."""

import os

from backend.services import file_storage


async def test_save_and_materialize_roundtrip(db):
    data = b"%PDF-1.4 fake invoice bytes"
    stored = await file_storage.save_file(db, "my invoice (final).pdf", data, "application/pdf")
    await db.commit()

    key = file_storage.file_key(stored)
    assert key.startswith("db://")

    # Fetch back from the DB
    fetched = await file_storage.get_file(db, key)
    assert fetched is not None
    assert fetched.data == data
    assert fetched.size == len(data)
    assert fetched.filename == "my_invoice_.final_.pdf" or fetched.filename.endswith(".pdf")

    # Materialize to a temp file for extraction libraries
    path = await file_storage.materialize(db, key)
    assert path is not None and os.path.exists(path)
    assert path.endswith(".pdf")
    with open(path, "rb") as f:
        assert f.read() == data
    os.remove(path)


async def test_sanitize_filename_blocks_path_traversal():
    assert "/" not in file_storage.sanitize_filename("../../etc/passwd")
    assert "\\" not in file_storage.sanitize_filename("..\\..\\backend\\main.py")
    assert file_storage.sanitize_filename("..\\..\\evil.py") == "evil.py"
    assert file_storage.sanitize_filename("") == "upload"


async def test_file_size_limit(db):
    import pytest

    with pytest.raises(file_storage.FileTooLargeError):
        await file_storage.save_file(db, "huge.pdf", b"x" * (file_storage.MAX_FILE_SIZE + 1))


async def test_materialize_legacy_local_path(db, tmp_path):
    """Old rows with plain local paths still work (backward compatible)."""
    f = tmp_path / "legacy.pdf"
    f.write_bytes(b"legacy")
    assert await file_storage.materialize(db, str(f)) == str(f)
    assert await file_storage.materialize(db, "uploads/does-not-exist.pdf") is None
    assert await file_storage.materialize(db, "db://not-a-uuid") is None

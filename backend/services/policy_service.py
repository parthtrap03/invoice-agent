from __future__ import annotations

"""Policy document ingestion (Phase 5).

Turns a real policy document (PDF) into structured `Policy` rows so the
compliance layer works off actual documents instead of only seeded text.
Splitting is deterministic: numbered headings and ALL-CAPS section titles.
"""

import os
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Policy
from backend.services.extraction_service import ExtractionError, PDFTextExtractor

# "1.", "2.3", "IV.", "A." style headings, or an ALL-CAPS title line
_NUMBERED_HEADING = re.compile(r"^\s*((?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])[.)])\s+(?P<title>[A-Z][^\n]{3,80})\s*$")
_CAPS_HEADING = re.compile(r"^\s*(?P<title>[A-Z][A-Z0-9 ,&/\-]{5,80})\s*$")

MAX_SECTIONS = 40
MAX_CONTENT_CHARS = 4000
MIN_CONTENT_CHARS = 60


def split_policy_sections(text: str) -> list[tuple[str, str]]:
    """Split raw policy text into (title, content) sections, deterministically."""
    sections: list[tuple[str, list[str]]] = []
    current_title: Optional[str] = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        m = _NUMBERED_HEADING.match(stripped) or _CAPS_HEADING.match(stripped)
        if m and len(stripped) <= 90:
            if current_title is not None:
                sections.append((current_title, current_lines))
            current_title = " ".join(m.group("title").split()).title()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections.append((current_title, current_lines))

    result: list[tuple[str, str]] = []
    for title, lines in sections:
        content = "\n".join(lines).strip()
        if len(content) < MIN_CONTENT_CHARS:
            continue
        result.append((title, content[:MAX_CONTENT_CHARS]))
        if len(result) >= MAX_SECTIONS:
            break
    return result


def _source_slug(file_path: str) -> str:
    stem = os.path.splitext(os.path.basename(file_path))[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    return slug[:20] or "DOC"


async def ingest_policy_document(
    db: AsyncSession,
    file_path: str,
    category: str = "Ingested Document",
    source_name: str | None = None,
) -> list[Policy]:
    """Parse a policy PDF and persist its sections as Policy rows.

    Idempotent per document: re-ingesting replaces that document's rows
    (matched by the policy_code prefix derived from the filename).
    """
    if not file_path.lower().endswith(".pdf"):
        raise ExtractionError(f"Only PDF policy documents are supported: {file_path}")

    text = PDFTextExtractor()._read_text(file_path)
    if not text.strip():
        raise ExtractionError(f"No extractable text in policy document: {file_path}")

    # Policy codes derive from the ORIGINAL document name (source_name), not
    # from a temp path the file may have been materialized to
    slug = _source_slug(source_name or file_path)

    sections = split_policy_sections(text)
    if not sections:
        # Fall back to one policy holding the whole document
        sections = [(slug.replace("-", " ").title(), text.strip()[:MAX_CONTENT_CHARS])]

    # Replace prior ingestion of the same document
    existing = (
        await db.execute(select(Policy).where(Policy.policy_code.like(f"DOC-{slug}-%")))
    ).scalars().all()
    for p in existing:
        await db.delete(p)
    await db.flush()  # deletes must hit the DB before same-code inserts

    created: list[Policy] = []
    for i, (title, content) in enumerate(sections, start=1):
        policy = Policy(
            policy_code=f"DOC-{slug}-{i:03d}",
            title=title[:120],
            category=category,
            content=content,
            version="1.0",
            is_active=True,
        )
        db.add(policy)
        created.append(policy)

    await db.commit()
    return created

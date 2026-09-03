from __future__ import annotations

"""Tests for the free/offline AI stack: local OCR for scanned images,
BM25 policy search, and graceful degradation when Ollama is absent."""

import importlib.util
import os

import pytest

from backend.services.extraction_service import ExtractionService
from backend.services.finance_service import _bm25_rank, _tokenize

HAS_RAPIDOCR = importlib.util.find_spec("rapidocr_onnxruntime") is not None
ARIAL = r"C:\Windows\Fonts\arial.ttf"


def _make_scanned_invoice(path: str) -> None:
    """Render a synthetic 'scanned' invoice image with PIL."""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(ARIAL, 32)
    img = Image.new("RGB", (1000, 700), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "TAX INVOICE",
        "Vendor: Scanned Traders Ltd",
        "Invoice No: INV-OCR-501",
        "PO Number: PO-777",
        "Date: 2026-08-15",
        "",
        "Subtotal: 40000.00",
        "GST (18%): 7200.00",
        "Grand Total: 47200.00",
    ]
    y = 40
    for line in lines:
        draw.text((60, y), line, fill="black", font=font)
        y += 60
    img.save(path)


# ---------------------------------------------------------------------------
# Local OCR (RapidOCR) - scanned image -> structured invoice, fully offline
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not HAS_RAPIDOCR, reason="rapidocr-onnxruntime not installed")
@pytest.mark.skipif(not os.path.exists(ARIAL), reason="no truetype font available")
async def test_ocr_extracts_scanned_invoice(tmp_path):
    img_path = str(tmp_path / "scanned-invoice.png")
    _make_scanned_invoice(img_path)

    result = await ExtractionService().extract(img_path)

    assert result.extraction_method in ("ocr_local", "ollama_vision") or result.extraction_method.startswith("ollama_vision")
    if result.extraction_method == "ocr_local":
        assert result.invoice_number == "INV-OCR-501"
        assert result.po_number == "PO-777"
        assert result.subtotal == 40000.00
        assert result.tax_amount == 7200.00
        assert result.total_amount == 47200.00
        assert 0.0 < result.confidence <= 1.0


async def test_image_extraction_never_crashes(tmp_path):
    """Even a garbage image must fall through to the mock, not raise."""
    img_path = tmp_path / "not-really-an-invoice.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)  # broken png

    result = await ExtractionService().extract(str(img_path))
    assert result.extraction_method == "mock"  # graceful last-resort fallback


# ---------------------------------------------------------------------------
# BM25 policy ranking (free RAG-lite)
# ---------------------------------------------------------------------------
def test_bm25_ranks_relevant_doc_highest():
    docs = [
        _tokenize("Duplicate payments must be detected and prevented before disbursement"),
        _tokenize("Travel expense reimbursement requires original receipts"),
        _tokenize("Vendors must be onboarded with a valid tax identification number"),
    ]
    scores = _bm25_rank(_tokenize("how do we prevent duplicate payments"), docs)
    assert scores[0] == max(scores)
    assert scores[0] > 0
    assert scores[1] == 0.0  # no overlapping terms


def test_tokenize_drops_stopwords():
    tokens = _tokenize("What is our policy for the duplicate invoices?")
    assert "duplicate" in tokens and "invoices" in tokens
    assert "what" not in tokens and "policy" not in tokens


# ---------------------------------------------------------------------------
# Graceful degradation without Ollama
# ---------------------------------------------------------------------------
async def test_rephrase_returns_none_without_ollama(monkeypatch):
    from backend.services import llm_service

    monkeypatch.setattr(llm_service.OllamaLLM, "_list_models_sync", lambda self: [])
    llm_service._llm = None  # reset singleton
    result = await llm_service.rephrase_answer("total spend?", "₹1,000.00 across 2 invoices.", [])
    assert result is None
    llm_service._llm = None

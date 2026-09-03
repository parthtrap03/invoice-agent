from __future__ import annotations

"""Tests for the free/offline extraction stack: local OCR for scanned images
and graceful degradation when no local LLM is available."""

import importlib.util
import os

import pytest

from backend.services.extraction_service import ExtractionService

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
# Graceful degradation without Ollama
# ---------------------------------------------------------------------------
async def test_vision_adapter_unavailable_without_ollama(monkeypatch, tmp_path):
    """With no local vision model, the adapter raises so the service falls
    through to OCR instead of failing the upload."""
    from backend.services import llm_service
    from backend.services.extraction_service import ExtractionError, OllamaVisionExtractionAdapter

    monkeypatch.setattr(llm_service.OllamaLLM, "_list_models_sync", lambda self: [])
    llm_service._llm = None  # reset singleton

    img = tmp_path / "scan.png"
    img.write_bytes(b"not a real png")
    with pytest.raises(ExtractionError):
        await OllamaVisionExtractionAdapter().extract(str(img))

    llm_service._llm = None

from __future__ import annotations

"""Tests for the Phase 2 document ingestion & extraction engine."""

from backend.services.extraction_service import (
    ExtractionService,
    MockExtractionAdapter,
    parse_invoice_text,
)

SAMPLE_TEXT = """
TAX INVOICE
Vendor: ABC Cloud Services
GSTIN: 27AABCU9603R1ZM
Invoice No: INV-88231
PO Number: PO-99182
Date: 2026-08-27
Due Date: 2026-09-26
Payment Terms: NET 30

Description                        Qty     Unit Price     Amount
Cloud Infrastructure Services      12      153333.33      1840000.00

Subtotal: 1,840,000.00
GST (18%): 331,200.00
Grand Total: 2,171,200.00
"""


def test_parse_invoice_text_extracts_fields():
    result = parse_invoice_text(SAMPLE_TEXT)

    assert result.invoice_number == "INV-88231"
    assert result.po_number == "PO-99182"
    assert result.vendor_name == "ABC Cloud Services"
    assert result.subtotal == 1840000.00
    assert result.tax_amount == 331200.00
    assert result.total_amount == 2171200.00
    assert result.invoice_date is not None and result.invoice_date.isoformat() == "2026-08-27"
    assert result.due_date is not None and result.due_date.isoformat() == "2026-09-26"
    assert result.payment_terms == "NET30"
    assert len(result.line_items) == 1
    item = result.line_items[0]
    assert item.description == "Cloud Infrastructure Services"
    assert item.quantity == 12
    assert item.unit_price == 153333.33


async def test_mock_adapter_demo_invoice():
    extracted = await MockExtractionAdapter().extract("uploads/INV-88231.pdf")

    assert extracted.invoice_number == "INV-88231"
    assert extracted.vendor_name == "ABC Cloud Services"
    assert extracted.po_number == "PO-99182"
    assert extracted.subtotal == 1840000.00
    assert extracted.tax_amount == 331200.00
    assert extracted.total_amount == 2171200.00
    assert extracted.currency == "INR"
    assert len(extracted.line_items) == 1
    assert extracted.line_items[0].quantity == 12


async def test_extraction_service_routes_demo_to_mock():
    extracted = await ExtractionService().extract("uploads/invoice-INV-88231-scan.png")
    assert extracted.extraction_method == "mock"
    assert extracted.invoice_number == "INV-88231"


async def test_extraction_service_falls_back_to_mock_for_unknown_files():
    extracted = await ExtractionService().extract("uploads/random-photo.png")
    assert extracted.extraction_method == "mock"
    assert extracted.invoice_number is not None

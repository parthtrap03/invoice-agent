from __future__ import annotations

"""Document ingestion & extraction engine (Phase 2).

Extracts raw text/tables from uploaded invoice documents (PDF/image) and
normalizes them into the structured `ExtractedInvoice` schema.

Adapters:
    - PDFTextExtractor:      local digital PDFs via pypdf (pdfplumber if available)
    - MockExtractionAdapter: deterministic offline extraction for demo invoices
    - BedrockExtractionAdapter: multimodal (image/scanned PDF) abstraction
"""

import abc
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

from backend.schemas.extraction import ExtractedInvoice, ExtractedLineItem


class ExtractionError(Exception):
    """Raised when a document cannot be extracted."""


class ExtractionAdapter(abc.ABC):
    """Interface every extraction backend implements."""

    name: str = "base"

    @abc.abstractmethod
    async def extract(self, file_path: str) -> ExtractedInvoice:
        """Extract a structured invoice from the document at `file_path`."""

    def supports(self, file_path: str) -> bool:
        return True


# ---------------------------------------------------------------------------
# PDF text extraction (digital PDFs)
# ---------------------------------------------------------------------------
class PDFTextExtractor(ExtractionAdapter):
    """Extracts text (and tables when pdfplumber is available) from digital PDFs."""

    name = "pdf_text"

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf")

    async def extract(self, file_path: str) -> ExtractedInvoice:
        raw_text = self._read_text(file_path)
        if not raw_text.strip():
            raise ExtractionError(f"No extractable text in PDF: {file_path}")
        invoice = parse_invoice_text(raw_text)
        invoice.extraction_method = self.name
        invoice.raw_text = raw_text
        return invoice

    def _read_text(self, file_path: str) -> str:
        # Prefer pdfplumber (better layout/tables), fall back to pypdf
        try:
            import pdfplumber

            text_parts: list[str] = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
                    for table in page.extract_tables() or []:
                        for row in table:
                            text_parts.append(" | ".join(c or "" for c in row))
            return "\n".join(text_parts)
        except ImportError:
            pass

        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ExtractionError("Neither pdfplumber nor pypdf is installed") from exc

        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------------------------------------------------------------------------
# Local OCR extraction for scanned images (free, offline - RapidOCR)
# ---------------------------------------------------------------------------
class OCRExtractionAdapter(ExtractionAdapter):
    """Extracts text from scanned images/photos using RapidOCR (ONNX, CPU,
    fully offline and free), then runs the same deterministic field parser
    used for digital PDFs."""

    name = "ocr_local"

    _engine = None  # lazy singleton; model load takes a moment

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"))

    @classmethod
    def _get_engine(cls):
        if cls._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise ExtractionError(
                    "RapidOCR is not installed (pip install rapidocr-onnxruntime)"
                ) from exc
            cls._engine = RapidOCR()
        return cls._engine

    async def extract(self, file_path: str) -> ExtractedInvoice:
        engine = self._get_engine()
        try:
            result, _ = engine(file_path)
        except Exception as exc:  # missing/corrupt image, engine failure
            raise ExtractionError(f"OCR could not read image {file_path}: {exc}") from exc
        if not result:
            raise ExtractionError(f"OCR found no text in image: {file_path}")

        # result rows: [box, text, confidence] - reconstruct lines top-to-bottom,
        # grouping boxes whose vertical centers are close (same visual line)
        rows = sorted(
            ((min(p[1] for p in box), min(p[0] for p in box), text, conf) for box, text, conf in result),
            key=lambda r: (r[0], r[1]),
        )
        lines: list[list[tuple[float, str]]] = []
        current_y: float | None = None
        for y, x, text, _conf in rows:
            if current_y is None or abs(y - current_y) > 12:
                lines.append([])
                current_y = y
            lines[-1].append((x, text))
        raw_text = "\n".join(
            " ".join(t for _, t in sorted(line)) for line in lines
        )

        avg_conf = sum(float(conf) for _, _, conf in result) / len(result)
        invoice = parse_invoice_text(raw_text)
        invoice.extraction_method = self.name
        invoice.raw_text = raw_text
        invoice.confidence = round(avg_conf, 3)
        return invoice


# ---------------------------------------------------------------------------
# Local LLM vision extraction (free, offline - Ollama, optional)
# ---------------------------------------------------------------------------
class OllamaVisionExtractionAdapter(ExtractionAdapter):
    """Uses a locally running Ollama vision model (llava / llama3.2-vision /
    qwen2.5vl) to read an invoice image into structured JSON. Zero cost, no
    API keys; raises ExtractionError when Ollama or a vision model is absent
    so the service falls through to OCR."""

    name = "ollama_vision"

    _PROMPT = (
        "You are an invoice data extractor. Read this invoice image and reply "
        "with ONLY a JSON object (no markdown, no commentary) with keys: "
        "invoice_number, vendor_name, vendor_tax_id, po_number, "
        "invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD), payment_terms, "
        "subtotal, tax_amount, total_amount, currency (3-letter code), "
        "line_items (array of {description, quantity, unit_price, total_price}). "
        "Use null for anything not visible. Numbers must be plain numbers "
        "without currency symbols or thousands separators."
    )

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))

    async def extract(self, file_path: str) -> ExtractedInvoice:
        from backend.services.llm_service import get_local_llm

        llm = get_local_llm()
        model = await llm.pick_model(vision=True)
        if model is None:
            raise ExtractionError("No local Ollama vision model available")

        response = await llm.generate(self._PROMPT, model=model, image_path=file_path)
        if not response:
            raise ExtractionError("Local vision model returned no output")

        try:
            start, end = response.index("{"), response.rindex("}") + 1
            payload = json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            raise ExtractionError(f"Vision model output was not valid JSON: {response[:200]}") from exc

        items = [
            ExtractedLineItem(
                description=str(li.get("description") or "Item"),
                quantity=int(li.get("quantity") or 1),
                unit_price=float(li.get("unit_price") or 0),
                total_price=float(li.get("total_price") or 0),
            )
            for li in payload.get("line_items") or []
            if isinstance(li, dict)
        ]
        invoice = ExtractedInvoice(
            invoice_number=payload.get("invoice_number"),
            vendor_name=payload.get("vendor_name"),
            vendor_tax_id=payload.get("vendor_tax_id"),
            po_number=payload.get("po_number"),
            invoice_date=_parse_date(str(payload.get("invoice_date") or "")),
            due_date=_parse_date(str(payload.get("due_date") or "")),
            payment_terms=payload.get("payment_terms"),
            line_items=items,
            subtotal=payload.get("subtotal"),
            tax_amount=payload.get("tax_amount"),
            total_amount=payload.get("total_amount"),
            currency=payload.get("currency") or "INR",
            extraction_method=f"{self.name}:{model}",
            confidence=0.85,
        )
        return invoice


# ---------------------------------------------------------------------------
# Mock extraction (offline / demo)
# ---------------------------------------------------------------------------
class MockExtractionAdapter(ExtractionAdapter):
    """Deterministic extraction for demo invoices — no external dependencies.

    Recognizes the primary demo invoice INV-88231 (ABC Cloud Services) by
    filename; anything else gets a generic deterministic payload derived
    from the filename so offline demos remain stable.
    """

    name = "mock"

    async def extract(self, file_path: str) -> ExtractedInvoice:
        filename = os.path.basename(file_path)
        if "88231" in filename.upper():
            return self._demo_invoice()
        return self._generic_invoice(filename)

    def _demo_invoice(self) -> ExtractedInvoice:
        today = date.today()
        return ExtractedInvoice(
            invoice_number="INV-88231",
            vendor_name="ABC Cloud Services",
            vendor_tax_id="GST-ABC123456",
            po_number="PO-99182",
            invoice_date=today - timedelta(days=5),
            due_date=today + timedelta(days=25),
            payment_terms="NET30",
            line_items=[
                ExtractedLineItem(
                    description="Cloud Infrastructure Services",
                    quantity=12,
                    unit_price=153333.33,
                    total_price=1840000.00,
                )
            ],
            subtotal=1840000.00,
            tax_amount=331200.00,
            total_amount=2171200.00,
            currency="INR",
            extraction_method=self.name,
            confidence=0.98,
        )

    def _generic_invoice(self, filename: str) -> ExtractedInvoice:
        stem = os.path.splitext(filename)[0]
        today = date.today()
        return ExtractedInvoice(
            invoice_number=f"INV-{stem.upper()[:20]}",
            vendor_name=None,
            invoice_date=today,
            due_date=today + timedelta(days=30),
            payment_terms="NET30",
            line_items=[
                ExtractedLineItem(description="Services", quantity=1, unit_price=10000.00, total_price=10000.00)
            ],
            subtotal=10000.00,
            tax_amount=1800.00,
            total_amount=11800.00,
            currency="INR",
            extraction_method=self.name,
            confidence=0.50,
        )


# ---------------------------------------------------------------------------
# Bedrock multimodal extraction (abstraction only — no network calls here)
# ---------------------------------------------------------------------------
class BedrockExtractionAdapter(ExtractionAdapter):
    """Multimodal extraction via AWS Bedrock (images / scanned PDFs).

    Abstraction over `bedrock-runtime`; instantiated lazily so the app runs
    fully offline. Callers should fall back to another adapter when boto3 or
    AWS credentials are unavailable.
    """

    name = "bedrock"

    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        from backend.config import get_settings

        settings = get_settings()
        self.model_id = model_id or settings.BEDROCK_MODEL_ID
        self.region = region or settings.AWS_REGION

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp"))

    async def extract(self, file_path: str) -> ExtractedInvoice:
        try:
            import boto3  # noqa: F401
        except ImportError as exc:
            raise ExtractionError("boto3 is not installed; Bedrock extraction unavailable") from exc
        raise ExtractionError(
            "BedrockExtractionAdapter is an abstraction stub in this environment; "
            "configure AWS credentials and implement invoke_model to enable it."
        )


# ---------------------------------------------------------------------------
# Text -> structured invoice parsing (deterministic heuristics)
# ---------------------------------------------------------------------------
# Amounts must sit on the SAME line as their label ([ \t] only, no newlines)
_AMOUNT = r"(?:₹|Rs\.?|INR|\$|USD|EUR|€)?[ \t]*([\d,]+(?:\.\d{1,2})?)"
# Numeric (2016-01-25, 25/01/2016, 11/15/2019) or textual (January 25, 2016) dates
_DATE = r"((?:\d{1,4}[-/]\d{1,2}[-/]\d{1,4})|(?:[A-Za-z]{3,9}\.?[ \t]+\d{1,2},?[ \t]+\d{4}))"

_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    # Either a label word (No/Number/#) with optional colon, or bare "Invoice:" with mandatory colon;
    # the captured token must contain a digit so header words are never mistaken for numbers.
    "invoice_number": re.compile(
        r"invoice\s*(?:(?:no\.?|number|#)\s*[:\-]?|[:\-])[ \t]*((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]+)", re.I
    ),
    "po_number": re.compile(
        r"(?:purchase\s*order|p\.?o\.?)\s*(?:(?:no\.?|number|#)\s*[:\-]?|[:\-])[ \t]*((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]+)", re.I
    ),
    "vendor_name": re.compile(r"(?:vendor|supplier|from|billed\s*by|sold\s*by)\s*[:\-][ \t]*\n?[ \t]*(.+)", re.I),
    "vendor_tax_id": re.compile(r"(?:gstin|gst|tax\s*id|vat)\s*(?:no\.?|number|#)?\s*[:\-][ \t]*([A-Z0-9\-]+)", re.I),
    "payment_terms": re.compile(r"(?:payment\s*)?terms\s*[:\-][ \t]*(NET[ \t]*\d+|[A-Za-z0-9 ]+)", re.I),
    "invoice_date": re.compile(r"(?:invoice\s*)?date\s*[:\-]?[ \t]*" + _DATE, re.I),
    "due_date": re.compile(r"due\s*(?:date)?\s*[:\-]?[ \t]*" + _DATE, re.I),
    # NOTE: [ \t] instead of \s inside these so a label at end-of-line never
    # grabs a number from the NEXT line (e.g. a table header above line items)
    "subtotal": re.compile(r"sub[ \t]*[- ]?total[ \t]*[:\-]?[ \t]*" + _AMOUNT, re.I),
    "tax_amount": re.compile(r"(?:sales[ \t]*tax|tax|gst|igst|cgst[ \t]*\+[ \t]*sgst)[ \t]*(?:\([ \t]*\d+(?:\.\d+)?[ \t]*%[ \t]*\))?[ \t]*[:\-]?[ \t]*" + _AMOUNT, re.I),
    "total_amount": re.compile(r"\b(?:grand[ \t]*total|total[ \t]*(?:amount|due)?)[ \t]*[:\-]?[ \t]*" + _AMOUNT, re.I),
}

# Fallback when no "PO Number: X" label pairs up (e.g. table layouts): a bare PO-#### token
_PO_TOKEN = re.compile(r"\b(PO-\d[\dA-Z\-]*)\b", re.I)
# Fallback terms like "Payment is due within 30 days"
_TERMS_FALLBACK = re.compile(r"due\s+within\s+(\d{1,3})\s+days", re.I)

# desc  qty  unit  total   |   qty  desc  unit  total  (currency symbols optional)
_LINE_ITEM = re.compile(
    r"^(?P<desc>[A-Za-z][A-Za-z0-9 .,&/()\-]{2,60}?)\s{1,}\|?\s*(?P<qty>\d{1,5})\s*\|?\s{1,}"
    + r"[₹$€]?(?P<unit>[\d,]+(?:\.\d{1,2})?)\s*\|?\s{1,}[₹$€]?(?P<total>[\d,]+(?:\.\d{1,2})?)\s*$",
)
_LINE_ITEM_QTY_FIRST = re.compile(
    r"^(?P<qty>\d{1,5})\s{1,}(?P<desc>[A-Za-z][A-Za-z0-9 .,&/()\-]{2,60}?)\s{1,}"
    + r"[₹$€]?(?P<unit>[\d,]+(?:\.\d{1,2})?)\s{1,}[₹$€]?(?P<total>[\d,]+(?:\.\d{1,2})?)\s*$",
)

# Trailing junk that leaks into vendor names from two-column PDF layouts
_VENDOR_NOISE = re.compile(r"\s+(?:order\s*number|invoice\s*(?:no|number|date)|due\s*date|total|gstin|date)\b.*$", re.I)

_DATE_FORMATS = (
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y",
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
)


def _parse_amount(value: str) -> float:
    return float(value.replace(",", ""))

def _parse_date(value: str) -> Optional[date]:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_invoice_text(text: str) -> ExtractedInvoice:
    """Normalize raw invoice text into `ExtractedInvoice` using regex heuristics."""
    fields: dict[str, object] = {}

    for key, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip()
        if key in ("subtotal", "tax_amount", "total_amount"):
            fields[key] = _parse_amount(value)
        elif key in ("invoice_date", "due_date"):
            parsed = _parse_date(value)
            if parsed:
                fields[key] = parsed
        elif key == "payment_terms":
            fields[key] = value.upper().replace(" ", "")[:20]
        elif key == "vendor_name":
            cleaned = _VENDOR_NOISE.sub("", value).strip(" |,-")
            if cleaned:
                fields[key] = cleaned[:100]
        else:
            fields[key] = value

    # Fallbacks for common real-world layouts
    if "po_number" not in fields:
        po_token = _PO_TOKEN.search(text)
        if po_token:
            fields["po_number"] = po_token.group(1).upper()
    else:
        # "PO-3333" can match the labeled pattern with "-" as separator,
        # capturing only "3333" — restore the full token if it exists verbatim
        po_val = str(fields["po_number"])
        if po_val.isdigit() and f"PO-{po_val}" in text.upper():
            fields["po_number"] = f"PO-{po_val}"
    if "payment_terms" not in fields:
        terms = _TERMS_FALLBACK.search(text)
        if terms:
            fields["payment_terms"] = f"NET{terms.group(1)}"

    line_items: list[ExtractedLineItem] = []
    for line in text.splitlines():
        m = _LINE_ITEM.match(line.strip()) or _LINE_ITEM_QTY_FIRST.match(line.strip())
        if not m:
            continue
        desc = m.group("desc").strip()
        if desc.lower() in ("subtotal", "total", "tax", "gst", "description"):
            continue
        line_items.append(
            ExtractedLineItem(
                description=desc,
                quantity=int(m.group("qty")),
                unit_price=_parse_amount(m.group("unit")),
                total_price=_parse_amount(m.group("total")),
            )
        )

    if re.search(r"₹|INR|Rs\.", text):
        fields["currency"] = "INR"
    elif re.search(r"\$|USD", text):
        fields["currency"] = "USD"
    elif re.search(r"€|EUR", text):
        fields["currency"] = "EUR"

    return ExtractedInvoice(line_items=line_items, **fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Service orchestrator
# ---------------------------------------------------------------------------
class ExtractionService:
    """Routes a document to the right adapter and returns structured data.

    Order of preference (all free / offline):
      1. MockExtractionAdapter for known demo documents (deterministic, offline)
      2. PDFTextExtractor for digital PDFs
      3. OllamaVisionExtractionAdapter for images, when a local Ollama vision
         model is running (free local LLM)
      4. OCRExtractionAdapter for images via RapidOCR (free local OCR)
      5. MockExtractionAdapter as a last-resort fallback so ingestion never 500s
    """

    def __init__(self, adapters: Optional[list[ExtractionAdapter]] = None):
        self.mock = MockExtractionAdapter()
        self.adapters: list[ExtractionAdapter] = adapters or [
            PDFTextExtractor(),
            OllamaVisionExtractionAdapter(),
            OCRExtractionAdapter(),
        ]

    async def extract(self, file_path: str) -> ExtractedInvoice:
        filename = os.path.basename(file_path).upper()
        if "88231" in filename or filename.startswith("DEMO"):
            return await self.mock.extract(file_path)

        for adapter in self.adapters:
            if not adapter.supports(file_path):
                continue
            try:
                return await adapter.extract(file_path)
            except ExtractionError:
                continue

        return await self.mock.extract(file_path)


def get_extraction_service() -> ExtractionService:
    return ExtractionService()

# Intelligent Finance & Invoice Agent

An Accounts Payable automation system: upload an invoice (PDF or scanned image), and
an agentic pipeline extracts it, runs five compliance checks, scores its risk, and
decides whether to auto-approve, route it for human review, or reject it — with a full
audit trail and step-by-step execution trace for every decision.

**Design principle: money decisions are deterministic.** Every calculation and rule
lives in plain, unit-tested Python — never in an LLM — so the same invoice always
produces the same decision and every flag can be explained in an audit.

## What it does

| Stage | Behaviour |
|---|---|
| **Ingest** | Digital PDFs via `pdfplumber`/`pypdf`; scanned images via local OCR (RapidOCR). Adapter chain falls back automatically, so ingestion never hard-fails |
| **Extract** | 12 fields — invoice/PO number, vendor, tax ID, dates, terms, line items, subtotal, tax, total, currency — from arbitrary layouts (no fixed templates) |
| **Validate** | `subtotal + tax == total`, 18% GST check, and line-item sum, all in `Decimal` with ₹1 tolerance |
| **Match** | 2-way PO match: PO active, vendor matches, line items match, amount variance vs. a 2% tolerance |
| **Detect duplicates** | Exact `(vendor, invoice_number)` match, plus fuzzy scoring on amount (±1%), date window (30 days) and invoice-number similarity |
| **Assess vendor** | Active status and a 0–100 vendor risk score (>70 = HIGH) |
| **Decide** | Weighted risk score (0–100) → `AUTO_APPROVE` / `REVIEW_REQUIRED` / `REJECT`, opening a pending approval when a human is needed |
| **Explain** | Every run is persisted as an `AgentRun` with per-step timings and outputs, plus audit rows for each action |

Also included: an approval → payment flow, and a policy-document ingestion pipeline
that splits a real policy PDF into a searchable library at `/api/policies`.

## Risk model

Weights are additive (max 100), and the bands are `LOW 0–30`, `MEDIUM 31–60`, `HIGH 61–100`.

| Violation | Points |
|---|---|
| Duplicate detected | 35 |
| PO variance > 2% | 30 |
| Inactive or high-risk vendor | 30 |
| Amount > ₹10,00,000 | 25 |
| Tax discrepancy | 15 |

Duplicates and inactive vendors are hard failures: they floor the score at 85 and force a
`REJECT`, since neither should ever reach a payment run.

## Tech stack

Python 3.11 · FastAPI · SQLAlchemy 2 (async) · Pydantic v2 · SQLite (any async
SQLAlchemy URL works) · React 19 · TypeScript · Vite · Tailwind · Docker · pytest

## Quick start

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

python setup_demo.py           # clean database + generate 5 demo invoice PDFs
uvicorn backend.main:app --reload
```

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

App at http://localhost:5173, API docs at http://localhost:8000/docs.

## Demo walkthrough

`setup_demo.py` generates five invoices in `uploads/demo/`, each crafted to exercise a
different path through the rules engine. Upload each one, then press **Process Invoice**.

| File | Expected outcome | Why |
|---|---|---|
| `01-clean-auto-approve.pdf` | `AUTO_APPROVE` | Matches PO-5001 exactly, correct 18% GST, under ₹10L |
| `02-po-variance-review.pdf` | `REVIEW_REQUIRED` | 2.22% over PO-99182 **and** above the ₹10L threshold |
| `03-wrong-gst-review.pdf` | `REVIEW_REQUIRED` | Billed at 5% GST instead of 18% |
| `04-inactive-vendor-reject.pdf` | `REJECT` | Vendor "Phantom Traders" is INACTIVE |
| `05-duplicate-reject.pdf` | approved, then `REJECT` | Upload and process it **twice** — the second copy is caught as a duplicate |

The Vendors and Purchase Orders pages show the master data these checks run against.

## Tests

```bash
pytest
```

29 tests covering the rules engine (one per decision path), field extraction against
real third-party invoice PDFs, the traced orchestrator, database file storage, and
policy ingestion.

## Deployment

The Docker image is self-contained: it builds the React app and serves it from the same
FastAPI process, so the whole system deploys as **one service on one URL** with no CORS
configuration and no separate frontend host.

```bash
docker build -t invoice-agent .
docker run -p 8000:8000 invoice-agent      # http://localhost:8000
```

On Render, `render.yaml` is picked up automatically — connect the repository and deploy;
`PORT` is injected by the platform. The database schema is created and seeded on startup,
so a fresh instance is immediately demo-ready.

Uploaded documents are stored **in the database** (`stored_files`) rather than on disk,
so nothing is lost when a container is replaced — the usual failure mode for file uploads
on ephemeral hosting.

## Project structure

```
backend/
  api/         FastAPI routers
  models/      SQLAlchemy models
  schemas/     Pydantic request/response models
  rules/       deterministic rules engine (tax, PO, duplicates, vendor, risk)
  services/    extraction, orchestration, file storage, policy ingestion
  seed.py      demo master data
frontend/      React + TypeScript UI
tests/         pytest suite
uploads/demo/  generated demo invoices
setup_demo.py  reset database + regenerate demo PDFs
```

## Design notes

- **Deterministic core, pluggable intelligence.** Extraction is an adapter interface
  (`PDFTextExtractor`, `OCRExtractionAdapter`, a local-LLM vision adapter, mock). A hosted
  vision model can be added as another adapter without touching the rules engine.
- **Idempotent decisions.** Re-processing an invoice recomputes results and never
  duplicates an open approval.
- **Storage is abstracted.** `source_file_key` is a `db://<id>` key, so swapping in S3
  later is a change in one service module.
- **Thresholds live in config, not in prose.** Policy documents are searchable
  knowledge, but enforcement values are explicit configuration — a parsed PDF should
  never be able to change what gets approved.

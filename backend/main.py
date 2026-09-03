from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from backend.config import get_settings
from backend.database import init_db, async_sessionmaker_factory
from backend.seed import seed_database
from backend.schemas.common import HealthResponse

from backend.api import invoices, vendors, purchase_orders, approvals, metrics, audit, agent_runs, finance, policies

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup (uploaded files live in the database, no local folder needed)
    await init_db()
    # Seed demo data
    async with async_sessionmaker_factory() as session:
        await seed_database(session)
    yield
    # Shutdown
    pass

app = FastAPI(
    title="Intelligent Finance & Invoice Agent",
    description="AI-powered Accounts Payable and Finance Operations",
    version="0.1.0",
    lifespan=lifespan
)

settings = get_settings()

# Only needed for local development, where Vite serves the UI on :5173.
# In production the same app serves the built frontend, so requests are
# same-origin and never hit CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router)
app.include_router(vendors.router)
app.include_router(purchase_orders.router)
app.include_router(approvals.router)
app.include_router(metrics.router)
app.include_router(audit.router)
app.include_router(agent_runs.router)
app.include_router(finance.router)
app.include_router(policies.router)

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.APP_ENV,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Sample invoices, so a deployed instance is demo-ready without cloning the repo
DEMO_FILES = PROJECT_ROOT / "uploads" / "demo"
if DEMO_FILES.is_dir():
    app.mount("/demo-files", StaticFiles(directory=DEMO_FILES), name="demo-files")


# ---------------------------------------------------------------------------
# Serve the built React app from this same service (single deployment).
# Absent in local dev - run `npm run dev` for the Vite server instead.
# ---------------------------------------------------------------------------
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve static files, falling back to index.html so client-side
        routes (/invoices/<id>, /approvals, ...) work on a hard refresh."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

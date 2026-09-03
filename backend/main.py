from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from backend.config import get_settings
from backend.database import init_db, async_sessionmaker_factory
from backend.seed import seed_database
from backend.schemas.common import HealthResponse

from backend.api import invoices, vendors, purchase_orders, approvals, metrics, audit, agent_runs

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

    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        """Serve index.html for unmatched non-API paths so client-side routes
        (/invoices/<id>, /approvals, ...) survive a hard refresh.

        Implemented as a middleware rather than a catch-all route so it never
        shadows the API - a catch-all would also swallow FastAPI's redirect
        from '/api/invoices' to '/api/invoices/'.
        """
        response = await call_next(request)
        if response.status_code == 404 and not request.url.path.startswith("/api"):
            return FileResponse(FRONTEND_DIST / "index.html")
        return response

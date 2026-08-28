from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI governance middleware for "
        "performance, cost and responsibility."
    ),
    version="4.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API ROUTES
# =========================================================

app.include_router(router)


# =========================================================
# DASHBOARD STATIC FILES
# =========================================================

if DASHBOARD_DIR.exists():

    app.mount(
        "/dashboard",
        StaticFiles(directory=str(DASHBOARD_DIR)),
        name="dashboard",
    )


# =========================================================
# ROOT — SERVE DASHBOARD
# =========================================================

@app.get("/", include_in_schema=False)
def root():

    dashboard_index = DASHBOARD_DIR / "index.html"

    if dashboard_index.exists():
        return FileResponse(dashboard_index)

    return {
        "service": settings.APP_NAME,
        "version": "4.0.0",
        "status": "running",
        "error": "Dashboard files not found",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/healthz", include_in_schema=False)
def healthz():

    return {
        "status": "healthy"
    }
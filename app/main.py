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

BASE_DIR = Path(
    __file__
).resolve().parent.parent


DASHBOARD_DIR = (
    BASE_DIR
    / "dashboard"
)


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
# CORS — CONTROLPLANE DASHBOARD
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# =========================================================
# DASHBOARD STATIC FILES
# =========================================================

app.mount(
    "/dashboard",
    StaticFiles(
        directory=str(
            DASHBOARD_DIR
        )
    ),
    name="dashboard",
)


# =========================================================
# DASHBOARD CSS
# =========================================================

@app.get(
    "/style.css"
)
def dashboard_css():

    return FileResponse(
        DASHBOARD_DIR
        / "style.css",

        media_type="text/css",
    )


# =========================================================
# DASHBOARD JAVASCRIPT
# =========================================================

@app.get(
    "/app.js"
)
def dashboard_js():

    return FileResponse(
        DASHBOARD_DIR
        / "app.js",

        media_type=(
            "application/javascript"
        ),
    )


# =========================================================
# API ROUTES
# =========================================================

app.include_router(
    router
)


# =========================================================
# ROOT — CONTROLPLANE DASHBOARD
# =========================================================

@app.get(
    "/",
    include_in_schema=False,
)
def root():

    return FileResponse(
        DASHBOARD_DIR
        / "index.html",

        media_type="text/html",
    )
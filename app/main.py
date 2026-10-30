import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings


logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("controlplane")


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
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
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
# SECURITY HEADERS + REQUEST TIMING
# =========================================================

@app.middleware("http")
async def security_headers_and_timing(
    request: Request,
    call_next,
):

    started = time.perf_counter()

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - started) * 1000

    response.headers.setdefault(
        "X-Content-Type-Options", "nosniff"
    )
    response.headers.setdefault(
        "X-Frame-Options", "DENY"
    )
    response.headers.setdefault(
        "Referrer-Policy", "no-referrer"
    )
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"

    # The dashboard is served unversioned, so make browsers revalidate
    # on every load (cheap 304s) and pick up new deploys immediately.
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")

    if request.url.path.startswith("/api/"):
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

    return response


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

def _versioned_index_html() -> str:
    """
    index.html with ?v=<file mtime> on its CSS/JS URLs.

    A browser that cached an older style.css / app.js would otherwise
    keep using it after a deploy; a changed file gets a new URL, so it
    is always downloaded.
    """

    html = (
        DASHBOARD_DIR / "index.html"
    ).read_text(encoding="utf-8")

    for name in ("style.css", "app.js"):

        version = int(
            (DASHBOARD_DIR / name).stat().st_mtime
        )

        html = html.replace(
            f'href="{name}"',
            f'href="{name}?v={version}"',
        ).replace(
            f'src="{name}"',
            f'src="{name}?v={version}"',
        )

    return html


@app.get(
    "/",
    include_in_schema=False,
)
def root():

    return HTMLResponse(
        _versioned_index_html()
    )
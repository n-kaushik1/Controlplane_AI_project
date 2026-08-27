from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings


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
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API ROUTES
# =========================================================

app.include_router(router)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "service": settings.APP_NAME,
        "version": "4.0.0",
        "status": "running"
    }
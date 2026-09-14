"""App wiring. Thin shell over routes."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from v2.api.routes import router as v2_router

from . import datasets
from .config import settings
from .routes import router

app = FastAPI(title="Dime NBA Analyst")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api")


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}

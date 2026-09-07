"""App wiring. Thin shell over routes."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from . import datasets
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


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}

"""App wiring. Thin shell over routes."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from v2.api.routes import router as v2_router, preflight_runtime_assets

from . import datasets, routes
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Freeze code, warehouse, and route prompt identity before accepting requests.
    preflight_runtime_assets()
    yield
    await routes.shutdown_shadow_tasks()


app = FastAPI(title="Dime NBA Analyst", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(routes.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api")


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}

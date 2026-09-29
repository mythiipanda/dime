from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from v2.api.routes import preflight_runtime_assets
from v2.api.routes import router as v2_router
from shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    preflight_runtime_assets()
    yield


app = FastAPI(title="Dime NBA Analyst (v2)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(v2_router, prefix="/api")


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs", "runtime": "v2"}

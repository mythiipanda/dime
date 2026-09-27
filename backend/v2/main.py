"""v2 standalone FastAPI entrypoint.

Step 2 of the v1-removal migration (Tony's directive: remove v1 entirely,
keep v2). Mounts only the v2 runtime (chat/stream, revision, projects)
with the same CORS + startup asset-preflight posture as the v1 shell, so
v2 can eventually serve without backend/app/.

NOT yet wired into the Dockerfile or any deploy path — the production
entrypoint remains app.main:app until the migration steps land. Run with:

    uvicorn v2.main:app --app-dir backend
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from v2.api.routes import preflight_runtime_assets
from v2.api.routes import router as v2_router
from shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Freeze code, warehouse, and route prompt identity before accepting requests.
    preflight_runtime_assets()
    yield


app = FastAPI(title="Dime NBA Analyst (v2)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(v2_router, prefix="/api")


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs", "runtime": "v2"}

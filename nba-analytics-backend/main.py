from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
import sys
import logging

# Configure root logger
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

if root_logger.hasHandlers():
    root_logger.handlers.clear()

root_logger.addHandler(console_handler)

from config import CORS_ALLOWED_ORIGINS
from routes.player import router as player_router
from routes.analyze import router as analyze_router
from routes.fetch import router as fetch_router
from routes.sse import router as sse_router

logger = logging.getLogger(__name__)

app = FastAPI(title="NBA Analytics Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(player_router)
app.include_router(analyze_router)
app.include_router(fetch_router)
app.include_router(sse_router)

@app.get("/")
async def root():
    return {"message": "NBA Analytics"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
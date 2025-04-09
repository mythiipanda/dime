import os
import sys
import logging
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add the backend directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add console handler to root logger
root_logger.addHandler(console_handler)

from config import CORS_ALLOWED_ORIGINS
from routes.player import router as player_router
from routes.analyze import router as analyze_router
from routes.sse import router as sse_router

app = FastAPI()

# Configure CORS with specific settings for SSE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly list allowed methods
    allow_headers=["*"],  # Allows all headers
    expose_headers=["Content-Type", "Content-Length"],  # Expose necessary headers for SSE
)

# Include routers
app.include_router(sse_router, tags=["sse"])  # Mount SSE router at root for /ask endpoint
app.include_router(player_router, prefix="/api", tags=["player"])  # Keep /api prefix for player routes
app.include_router(analyze_router, prefix="/api/analyze", tags=["analyze"])

@app.get("/")
async def root():
    return {"message": "Welcome to the NBA Stats API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
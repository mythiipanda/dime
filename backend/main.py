import os
import sys
import logging
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

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
from routes.team import router as team_router
from routes.game import router as game_router
from routes.player_tracking import router as player_tracking_router
from routes.team_tracking import router as team_tracking_router
from routes.standings import router as standings_router # Import standings router

app = FastAPI()

# Configure CORS with specific settings for SSE
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type", "Content-Length"],
)

# Include routers
app.include_router(sse_router, tags=["sse"])  # Mount SSE router at root for /ask endpoint
app.include_router(player_router, prefix="/api", tags=["player"])
app.include_router(analyze_router, prefix="/api/analyze", tags=["analyze"])
app.include_router(team_router, prefix="/api/team", tags=["team"])
app.include_router(game_router, prefix="/api/game", tags=["game"])
app.include_router(player_tracking_router, prefix="/api/player-tracking", tags=["player-tracking"])
app.include_router(team_tracking_router, prefix="/api/team-tracking", tags=["team-tracking"])
app.include_router(standings_router, prefix="/api", tags=["standings"]) # Register standings router

@app.get("/")
async def root():
    return {"message": "Welcome to the NBA Stats API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
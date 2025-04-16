import os
import sys
import logging
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

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

from backend.config import CORS_ALLOWED_ORIGINS
from backend.routes.player import router as player_router
from backend.routes.analyze import router as analyze_router
from backend.routes.sse import router as sse_router
from backend.routes.team import router as team_router
from backend.routes.game import router as game_router
from backend.routes.player_tracking import router as player_tracking_router
from backend.routes.team_tracking import router as team_tracking_router
from backend.routes.standings import router as standings_router
from backend.routes.live_game import router as live_game_router
from backend.routes.scoreboard import router as scoreboard_router

app = FastAPI(
    title="NBA Analytics API",
    description="API for fetching NBA player, team, game stats, and interacting with an AI agent.",
    version="0.1.0",
)

# Configure CORS
origins = [
    "http://localhost:3000",  # Allow frontend origin
    "http://127.0.0.1:3000",
    os.environ.get("FRONTEND_URL"), # Allow configured frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in origins if origin], # Filter out None/empty origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# Include routers
API_PREFIX = "/api/v1"

# Add legacy alias for ask endpoint under /api
app.include_router(sse_router, prefix="/api", tags=["sse_legacy"])
# Mount SSE router under versioned API prefix
app.include_router(sse_router, prefix=API_PREFIX, tags=["sse"])  # Mount SSE router under /api/v1 prefix
app.include_router(player_router, prefix=API_PREFIX + "/players", tags=["Players"])
# app.include_router(analyze_router, prefix="/api/analyze", tags=["analyze"]) # Removed analyze router
app.include_router(team_router, prefix=API_PREFIX + "/teams", tags=["Teams"])
app.include_router(game_router, prefix=API_PREFIX + "/games", tags=["Games"])
app.include_router(player_tracking_router, prefix=API_PREFIX + "/player/tracking", tags=["player_tracking"])
app.include_router(team_tracking_router, prefix=API_PREFIX + "/team/tracking", tags=["team_tracking"])
# Standings endpoint under versioned API prefix
app.include_router(standings_router, prefix=API_PREFIX, tags=["Standings"])
app.include_router(live_game_router, prefix=API_PREFIX + "/live", tags=["live"]) # Register live game router
app.include_router(scoreboard_router, prefix=API_PREFIX + "/scoreboard", tags=["Scoreboard"]) # Include scoreboard router

@app.get("/")
async def root():
    return {"message": "Welcome to the NBA Stats API"}

@app.get("/health", tags=["Health"])
async def health_check():
    root_logger.info("Health check endpoint called.")
    return {"status": "healthy"}

# Add more global exception handlers if needed
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    root_logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return HTTPException(status_code=500, detail="Internal server error")

# --- Add Route Printing Here ---
if __name__ == "__main__":
    # Print registered routes for debugging
    print("--- Registered Routes ---")
    for route in app.routes:
        if hasattr(route, "path"):
            print(f"Path: {route.path}, Name: {getattr(route, 'name', 'N/A')}, Methods: {getattr(route, 'methods', 'N/A')}")
        elif hasattr(route, "routes") and isinstance(route.routes, list):
             # Handle mounted routers/apps
             print(f"Mounted Router/App at: {route.path}")
             for sub_route in route.routes:
                 if hasattr(sub_route, "path"):
                    print(f"  Path: {sub_route.path}, Name: {getattr(sub_route, 'name', 'N/A')}, Methods: {getattr(sub_route, 'methods', 'N/A')}")
    print("-----------------------")
    
    root_logger.info("Starting NBA Analytics API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
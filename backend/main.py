import sys
import logging
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
from routes.team import router as team_router
from routes.game import router as game_router
from routes.search import router as search_router

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(player_router, prefix="/api/player", tags=["player"])
app.include_router(analyze_router, prefix="/api/analyze", tags=["analyze"])
app.include_router(team_router, prefix="/api/team", tags=["team"])
app.include_router(game_router, prefix="/api/game", tags=["game"])
app.include_router(search_router, prefix="/api/search", tags=["search"])

@app.get("/")
async def root():
    return {"message": "Welcome to the NBA Stats API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
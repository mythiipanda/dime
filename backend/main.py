"""
Main application file for the NBA Analytics FastAPI backend.
Initializes the FastAPI application, configures logging, middleware (CORS),
imports and includes API routers, and defines global exception handlers
and basic health check endpoints.
"""
import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Request, status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse # Moved imports to top
import uvicorn

# --- Python Path Setup ---
# Ensures the backend directory and its parent are in the Python path
# for consistent module resolution, especially when running main.py directly.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir) # Insert at beginning to prioritize project modules
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# --- Logging Configuration ---
# Import and apply centralized logging configuration.
# This must be done early, before other modules (which might use logging) are imported.
try:
    from backend.logging_config import setup_logging
    from backend.config import settings # settings is used for log level
    
    # Determine log level from settings (AGENT_DEBUG_MODE implies DEBUG level for app)
    log_level_str = "DEBUG" if settings.AGENT_DEBUG_MODE else settings.LOG_LEVEL
    setup_logging(log_level_override=log_level_str) # Pass string level to setup_logging
    logger = logging.getLogger(__name__) # Logger for this main module
    logger.info(f"Logging configured. Effective level: {logging.getLevelName(logger.getEffectiveLevel())}")

except ImportError as e:
    # Fallback to basicConfig if logging_config is missing or fails.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    logger.critical(f"CRITICAL: Failed to import or apply logging_config from backend.logging_config. Falling back to basicConfig. Error: {e}", exc_info=True)
    # Consider if sys.exit(1) is appropriate here or if the app should attempt to run with basic logging.
    # For now, allowing it to proceed with a critical log.

# --- Import Configuration and Routers ---
# These are imported after logging is set up.
try:
    # settings is already imported above for logging.
    from backend.core.errors import Errors
    from backend.routes import ( # Grouped router imports
        player as player_router,
        analyze as analyze_router,
        sse as sse_router,
        team as team_router,
        game as game_router,
        player_tracking as player_tracking_router,
        team_tracking as team_tracking_router,
        standings as standings_router,
        live_game as live_game_router,
        scoreboard as scoreboard_router,
        odds as odds_router,
        search as search_router,
        leaders as leaders_router,
        fetch as fetch_router # Added fetch_router
        # from backend.routes.charts import router as charts_router # Example, keep commented if not used
    )
except ImportError as e:
    logger.critical(f"Failed to import application modules (config/routers). This is a fatal error. Error: {e}", exc_info=True)
    sys.exit(1) # Exit if critical modules cannot be imported.


# --- FastAPI Application Initialization ---
app = FastAPI(
    title="Dime NBA Analytics API",
    description="API for fetching comprehensive NBA player, team, and game statistics, "
                "live scores, odds, and interacting with an AI-powered analytics agent.",
    version="0.2.2", # Incremented version
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)


# --- CORS Middleware Configuration ---
if not settings.CORS_ALLOWED_ORIGINS:
    logger.warning("settings.CORS_ALLOWED_ORIGINS is not set or empty in config. CORS will be restrictive.")
    effective_cors_origins = [] # Restrictive default
else:
    effective_cors_origins = settings.CORS_ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all standard methods
    allow_headers=["*"], # Allows all headers
)
logger.info(f"CORS middleware configured with origins: {effective_cors_origins}")

# --- API Router Inclusion ---
API_V1_PREFIX = "/api/v1"

app.include_router(sse_router.router, prefix=API_V1_PREFIX, tags=["SSE Agent Stream"]) # Added tag
app.include_router(player_router.router, prefix=API_V1_PREFIX, tags=["Player Data"]) # Added tag
app.include_router(player_tracking_router.router, prefix=API_V1_PREFIX + "/player", tags=["Player Tracking Data"]) # Added tag, adjusted prefix
app.include_router(analyze_router.router, prefix=API_V1_PREFIX + "/analyze", tags=["Analysis Tools"]) # analyze_router has internal /player
app.include_router(team_router.router, prefix=API_V1_PREFIX, tags=["Team Data"]) # Added tag
app.include_router(team_tracking_router.router, prefix=API_V1_PREFIX + "/team", tags=["Team Tracking Data"]) # Added tag, adjusted prefix
app.include_router(game_router.router, prefix=API_V1_PREFIX, tags=["Game Data"]) # Added tag
app.include_router(standings_router.router, prefix=API_V1_PREFIX, tags=["League Standings"]) # Added tag
app.include_router(leaders_router.router, prefix=API_V1_PREFIX, tags=["League Leaders"]) # Added tag
app.include_router(live_game_router.router, prefix=API_V1_PREFIX, tags=["Live Game Data"]) # Added tag
app.include_router(scoreboard_router.router, prefix=API_V1_PREFIX, tags=["Scoreboard"]) # Added tag
app.include_router(odds_router.router, prefix=API_V1_PREFIX, tags=["Odds"]) # Added tag
app.include_router(search_router.router, prefix=API_V1_PREFIX, tags=["Search"]) # Added tag
app.include_router(fetch_router.router, prefix=API_V1_PREFIX) # fetch_router already has /fetch prefix internally
# app.include_router(charts_router, prefix=API_V1_PREFIX, tags=["Visualizations"]) # Example

logger.info("All API routers included under /api/v1 prefix.")

# --- Basic Endpoints ---
@app.get("/", include_in_schema=False)
async def root_redirect_to_docs() -> RedirectResponse: # Added return type hint
    return RedirectResponse(url=str(app.docs_url)) # Ensure URL is string

@app.get("/health", tags=["Health Check"], summary="API Health Status")
async def health_check() -> dict: # Added return type hint
    logger.info("Health check endpoint called successfully.")
    return {"status": "healthy", "message": "NBA Analytics API is up and running!"}

# --- Global Exception Handler ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse: # Added return type hint
    logger.error(f"HTTPException caught: Status Code: {exc.status_code}, Detail: {exc.detail} for URL: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse: # Added return type hint
    logger.critical(f"Unhandled generic exception: {type(exc).__name__} - {exc} for URL: {request.url.path}", exc_info=True)
    
    error_content = Errors.UNEXPECTED_ERROR.format(error="An internal server error occurred.") \
        if hasattr(Errors, 'UNEXPECTED_ERROR') and '{error}' in Errors.UNEXPECTED_ERROR \
        else "An internal server error occurred. Please contact support." # More user-friendly fallback
        
    return JSONResponse(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_content},
    )

# --- Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event() -> None: # Added return type hint
    logger.info("NBA Analytics API starting up...")
    # Potential future startup tasks: Initialize DB connections, load ML models, etc.
    pass

@app.on_event("shutdown")
async def shutdown_event() -> None: # Added return type hint
    logger.info("NBA Analytics API shutting down...")
    # Potential future shutdown tasks: Close DB connections, save state, etc.
    pass

# --- Uvicorn Runner ---
if __name__ == "__main__":
    logger.info("--- Registered Routes ---")
    for route in app.routes:
        if hasattr(route, "path"): # Check if it's a routable object
            methods_str = ", ".join(sorted(list(getattr(route, 'methods', None) or set())))
            name_str = getattr(route, 'name', 'N/A')
            logger.info(f"Path: {route.path}, Name: {name_str}, Methods: [{methods_str}]")
    logger.info("-----------------------")
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000)) # Ensure PORT is integer
    reload_app = settings.ENVIRONMENT == "development" # Simpler reload logic based on ENVIRONMENT
    
    log_level_for_uvicorn = settings.LOG_LEVEL.lower()
    if log_level_for_uvicorn not in ["critical", "error", "warning", "info", "debug", "trace"]:
        log_level_for_uvicorn = "info" # Default for uvicorn if invalid

    logger.info(f"Starting NBA Analytics API server with Uvicorn on http://{host}:{port} (Reload: {reload_app}, Log Level: {log_level_for_uvicorn})...")
    uvicorn.run(
        "main:app", # app_module:app_variable
        host=host,
        port=port,
        reload=reload_app,
        log_level=log_level_for_uvicorn
    )
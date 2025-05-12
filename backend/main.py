import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# --- Python Path Setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- Logging Configuration ---
# Import and apply centralized logging configuration
try:
    from backend.logging_config import setup_logging
    from backend.config import settings # Changed
    
    # Determine log level based on debug mode
    log_level = logging.DEBUG if settings.AGENT_DEBUG_MODE else logging.INFO # Changed
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__) # Logger for this main module
    logger.info(f"Logging configured with level: {logging.getLevelName(log_level)}")

except ImportError as e:
    # Fallback to basicConfig if logging_config is missing or fails, though this shouldn't happen
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import or apply logging_config, falling back to basicConfig. Error: {e}", exc_info=True)
    sys.exit(1) # Exit if critical config like logging fails

# --- Import Configuration and Routers ---
try:
    from backend.config import settings # Changed (CORS_ALLOWED_ORIGINS will be settings.CORS_ALLOWED_ORIGINS)
    from backend.core.errors import Errors # Changed
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
    from backend.routes.odds import router as odds_router
    from backend.routes.search import router as search_router
    from backend.routes.leaders import router as leaders_router
    # from backend.routes.charts import router as charts_router # Example
except ImportError as e:
    logger.critical(f"Failed to import application modules (config/routers). Error: {e}", exc_info=True)
    sys.exit(1)


# --- FastAPI Application Initialization ---
app = FastAPI(
    title="Dime NBA Analytics API",
    description="API for fetching comprehensive NBA player, team, and game statistics, "
                "live scores, odds, and interacting with an AI-powered analytics agent.",
    version="0.2.1", # Incremented version
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)


# --- CORS Middleware Configuration ---
if not settings.CORS_ALLOWED_ORIGINS: # Changed
    logger.warning("settings.CORS_ALLOWED_ORIGINS is not set or empty in config. Defaulting to restrictive CORS.") # Changed
    effective_cors_origins = []
else:
    effective_cors_origins = settings.CORS_ALLOWED_ORIGINS # Changed

app.add_middleware(
    CORSMiddleware,
    allow_origins=effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS middleware configured with origins: {effective_cors_origins}")
# --- API Router Inclusion ---
API_V1_PREFIX = "/api/v1"

app.include_router(sse_router, prefix=API_V1_PREFIX)
app.include_router(player_router, prefix=API_V1_PREFIX)
app.include_router(player_tracking_router, prefix=API_V1_PREFIX)
app.include_router(analyze_router, prefix=API_V1_PREFIX + "/analyze") # analyze_router has internal /player
app.include_router(team_router, prefix=API_V1_PREFIX)
app.include_router(team_tracking_router, prefix=API_V1_PREFIX)
app.include_router(game_router, prefix=API_V1_PREFIX)
app.include_router(standings_router, prefix=API_V1_PREFIX)
app.include_router(leaders_router, prefix=API_V1_PREFIX)
app.include_router(live_game_router, prefix=API_V1_PREFIX)
app.include_router(scoreboard_router, prefix=API_V1_PREFIX)
app.include_router(odds_router, prefix=API_V1_PREFIX)
app.include_router(search_router, prefix=API_V1_PREFIX)
# app.include_router(charts_router, prefix=API_V1_PREFIX) # Example

logger.info("All API routers included under /api/v1 prefix.")

# --- Basic Endpoints ---
@app.get("/", include_in_schema=False)
async def root_redirect_to_docs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=app.docs_url) # Use app.docs_url

@app.get("/health", tags=["Health Check"], summary="API Health Status")
async def health_check():
    logger.info("Health check endpoint called successfully.")
    return {"status": "healthy", "message": "NBA Analytics API is up and running!"}

# --- Global Exception Handler ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException caught: Status Code: {exc.status_code}, Detail: {exc.detail} for URL: {request.url.path}")
    from fastapi.responses import JSONResponse # Local import
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_unhandled_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Unhandled generic exception: {type(exc).__name__} - {exc} for URL: {request.url.path}", exc_info=True)
    from fastapi.responses import JSONResponse
    from fastapi import status as http_status
    
    error_content = Errors.UNEXPECTED_ERROR.format(error="An internal server error occurred.") \
        if hasattr(Errors, 'UNEXPECTED_ERROR') and '{error}' in Errors.UNEXPECTED_ERROR \
        else "An internal server error occurred."
        
    return JSONResponse(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_content},
    )

# --- Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    logger.info("NBA Analytics API starting up...")
    pass

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("NBA Analytics API shutting down...")
    pass

# --- Uvicorn Runner ---
if __name__ == "__main__":
    logger.info("--- Registered Routes ---")
    for route in app.routes:
        if hasattr(route, "path"):
            methods = getattr(route, 'methods', None)
            name = getattr(route, 'name', 'N/A')
            logger.info(f"Path: {route.path}, Name: {name}, Methods: {methods}")
    logger.info("-----------------------")
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload_app = os.getenv("RELOAD_APP", "true").lower() == "true" # Changed env var name for clarity
    
    logger.info(f"Starting NBA Analytics API server with Uvicorn on {host}:{port} (Reload: {reload_app})...")
    uvicorn.run(
        "main:app",
        host=host, 
        port=port, 
        reload=reload_app,
        log_level=logging.getLevelName(logger.getEffectiveLevel()).lower()
    )
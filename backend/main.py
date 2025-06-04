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

try:
    from logging_config import setup_logging
    from config import settings
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
    logger.critical(f"CRITICAL: Failed to import or apply logging_config. Falling back to basicConfig. Error: {e}", exc_info=True)

try:
    from core.errors import Errors
    from routes.sse import router as sse_router

except ImportError as e:
    logger.critical(f"Failed to import application modules (config/routers). This is a fatal error. Error: {e}", exc_info=True)
    sys.exit(1)


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
# Correctly configure CORS based on settings or provide a secure default.
# It's crucial to define specific origins in your .env for production.
# For development, if settings.CORS_ALLOWED_ORIGINS is empty, a permissive policy might be used with a warning.
# However, for production, settings.CORS_ALLOWED_ORIGINS should be explicitly set.

# Enable CORS for development with Next.js frontend
allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
logger.info(f"CORS middleware configured. Allowed origins: {allow_origins}")

# --- API Router Inclusion ---
API_V1_PREFIX = "/api/v1"

# Include only the SSE router for now
if 'sse_router' in locals() and sse_router: 
    app.include_router(sse_router, prefix=API_V1_PREFIX)
    logger.info(f"SSE router included at {API_V1_PREFIX}/agent/stream.")
else:
    logger.warning("sse_router was not imported or is None. SSE endpoint will not be available.")


logger.info("API routers included under /api/v1 prefix. Some routers are temporarily disabled.")

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
    logger.error(f"HTTPException: {exc.status_code} {exc.detail} for URL: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse: # Added return type hint
    logger.critical(f"Unhandled exception: {type(exc).__name__} - {exc} for URL: {request.url.path}", exc_info=True)

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
    logger.info("Starting Uvicorn server...")
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,  # Set to False in production
            log_level="info" # Uvicorn's log level, separate from app's logger
        )
    except Exception as e:
        logger.critical(f"Failed to start Uvicorn server: {e}", exc_info=True)
        sys.exit(1)
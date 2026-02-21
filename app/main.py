from fastapi import FastAPI
from app.api import transcription, health, auth
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, close_db

# Setup logging
setup_logging(settings.log_level)
logger = get_logger("main")

app = FastAPI(
    title="Video Transcription System",
    description="AI-powered video transcription with emotion and tone analysis",
    version="1.0.0"
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])
app.include_router(health.router, tags=["health"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Video Transcription API")
    # Initialize database (for development - use Alembic in production)
    if settings.debug:
        await init_db()
        logger.info("Database initialized")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Video Transcription API")
    await close_db()

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Video Transcription API",
        "version": "1.0.0",
        "docs": "/docs"
    }
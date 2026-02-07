from fastapi import FastAPI
from app.api import transcription, health
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

# Setup logging
setup_logging(settings.log_level)
logger = get_logger("main")

app = FastAPI(
    title="Video Transcription System",
    description="AI-powered video transcription with emotion and tone analysis",
    version="1.0.0"
)

# Include routers
app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])
app.include_router(health.router, tags=["health"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Video Transcription API")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Video Transcription API")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Video Transcription API",
        "version": "1.0.0",
        "docs": "/docs"
    }
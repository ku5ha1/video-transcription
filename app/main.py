from fastapi import FastAPI
from app.api import transcription
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from celery.result import AsyncResult
from app.core.celery import celery_app, heavy_lifting_task

# Setup logging
setup_logging(settings.log_level)
logger = get_logger("main")

app = FastAPI(
    title="Video Transcription System",
    description="AI-powered video transcription with emotion and tone analysis"
)

app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Video Transcription API")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Video Transcription API")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Video Transcription API"}

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy", "service": settings.app_name}

@app.post("/run-task/{name}")
async def run_task(name: str):
    task = heavy_lifting_task.delay(name)
    return {"task_id": task.id, "status": "Task submitted to the kitchen!"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status, 
        "result": result.result  
    }
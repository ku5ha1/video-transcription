from fastapi import FastAPI
from app.api import transcription
from app.core.config import settings

app = FastAPI(
    title="Video Transcription System",
    description="AI-powered video transcription with emotion and tone analysis"
)

app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])

@app.get("/")
async def root():
    return {"message": "Video Transcription API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
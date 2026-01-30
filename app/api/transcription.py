from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.transcription import TranscriptionResponse
from app.services.transcription_service import TranscriptionService

router = APIRouter()
transcription_service = TranscriptionService()

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(file: UploadFile = File(...)):
    """
    Upload a video file and get transcription with emotion/tone analysis
    """
    if not file.filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
        raise HTTPException(status_code=400, detail="Invalid file format. Only video files are supported.")
    
    try:
        result = await transcription_service.process_video(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/status/{task_id}")
async def get_transcription_status(task_id: str):
    """
    Get the status of a transcription task
    """
    # Placeholder for future async task tracking
    return {"task_id": task_id, "status": "completed"}
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.services.chat_service import ChatService
from app.core.dependencies import get_current_user
from app.models.database import User
from app.core.logging import get_logger

logger = get_logger("api.chat")
router = APIRouter()
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Lazily initialize ChatService to avoid heavy import-time side effects."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


class ChatRequest(BaseModel):
    query: str
    video_id: Optional[str] = None
    history: Optional[List[dict]] = None


class SourceSegment(BaseModel):
    text: str
    timestamp: str
    speaker: str
    score: float
    video_id: str


class ChatResponse(BaseModel):
    answer: str
    source_segments: List[SourceSegment]
    query: str
    retrieved_segments_count: Optional[int] = None
    error: Optional[str] = None


@router.post("/chat/{video_id}", response_model=ChatResponse)
async def chat_with_video(
    video_id: str, request: ChatRequest, current_user: User = Depends(get_current_user)
):
    """
    Chat with video content using RAG

    - **video_id**: The video to chat about
    - **query**: Your question about the video content
    - **video_id** (optional): Limit search to specific video

    Returns AI-generated answer with source citations
    """
    logger.info(f"Chat request from {current_user.email} for video {video_id}")

    # Validate video access
    # Note: In production, you'd want to verify the user has access to this video
    # For now, we trust the user_id filtering in vector search

    # Process chat query
    result = await get_chat_service().chat(
        query=request.query,
        user_id=str(current_user.id),
        video_id=video_id,
        history=request.history,
        limit=5,
    )

    return result


@router.post("/chat", response_model=ChatResponse)
async def chat_general(
    request: ChatRequest, current_user: User = Depends(get_current_user)
):
    """
    General chat (searches across all user's videos)

    - **query**: Your question
    - **video_id** (optional): Limit search to specific video

    Returns AI-generated answer with source citations
    """
    logger.info(f"General chat request from {current_user.email}")

    result = await get_chat_service().chat(
        query=request.query,
        user_id=str(current_user.id),
        video_id=request.video_id,
        history=request.history,
        limit=5,
    )

    return result

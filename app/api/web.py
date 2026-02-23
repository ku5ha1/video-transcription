from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password, create_access_token
from app.models.database import User, Video
from app.utils.file_hash import calculate_file_hash
from app.core.logging import get_logger

logger = get_logger("api.web")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Initialize limiter for this router
limiter = Limiter(key_func=get_remote_address)


def get_current_user_optional(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current user from cookie, return None if not authenticated"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Fetch user synchronously (we'll need to make this async)
        import asyncio
        result = asyncio.create_task(db.execute(select(User).where(User.id == user_id)))
        user = asyncio.run(result).scalar_one_or_none()
        return user
    except Exception:
        return None


async def get_current_user_from_cookie(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current user from cookie, raise exception if not authenticated"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from app.core.security import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Process login form"""
    result = await db.execute(select(User).where(User.email == username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=400
        )
    
    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Account is inactive"},
            status_code=400
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # Redirect to home with cookie
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days
        samesite="lax"
    )
    
    logger.info(f"User logged in: {user.email}")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Process registration form"""
    
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match"},
            status_code=400
        )
    
    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered"},
            status_code=400
        )
    
    # Create new user
    hashed_pwd = hash_password(password)
    new_user = User(email=email, hashed_password=hashed_pwd)
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(f"New user registered: {email}")
    
    # Auto-login after registration
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        samesite="lax"
    )
    
    return response


@router.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Upload page"""
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)
    
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "user": current_user
        }
    )


@router.get("/video/{video_id}", response_class=HTMLResponse)
async def video_detail(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Video detail page with interactive transcript"""
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)
    
    # Fetch video with segments
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Video)
        .options(selectinload(Video.transcript_segments))
        .where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Sort segments by start_time
    segments = sorted(video.transcript_segments, key=lambda s: s.start_time)
    
    return templates.TemplateResponse(
        "video_detail.html",
        {
            "request": request,
            "user": current_user,
            "video": video,
            "segments": segments
        }
    )


@router.post("/api/web/chat/{video_id}")
async def web_chat(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Web chat endpoint using cookie authentication with history persistence"""
    from app.models.database import ChatMessage, ChatRole
    
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        return {"error": "Not authenticated"}
    
    try:
        # Get request body
        body = await request.json()
        query = body.get("query", "")
        
        if not query:
            return {"error": "Query is required"}
        
        # Fetch last 20 messages for context
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.video_id == video_id,
                ChatMessage.user_id == current_user.id
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
        )
        messages = result.scalars().all()
        
        # Format history for Gemini (reverse to chronological order)
        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.role,
                "parts": [{"text": msg.content}]
            })
        
        # Save user message with lowercase role
        user_message = ChatMessage(
            video_id=video_id,
            user_id=current_user.id,
            role="user",
            content=query
        )
        db.add(user_message)
        await db.commit()
        
        # Call chat service
        from app.services.chat_service import ChatService
        chat_service = ChatService()
        
        result = chat_service.chat(
            query=query,
            user_id=str(current_user.id),
            video_id=video_id,
            history=history,
            limit=5
        )
        
        # Save assistant response with lowercase role
        assistant_message = ChatMessage(
            video_id=video_id,
            user_id=current_user.id,
            role="assistant",
            content=result.get("answer", "")
        )
        db.add(assistant_message)
        await db.commit()
        
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Chat error: {e}", exc_info=True)
        return {"error": "Failed to process chat request"}


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Video library view"""
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)
    
    logger.info(f"Video library accessed by {current_user.email}")  # nosec B608
    
    # Fetch user's videos
    result = await db.execute(
        select(Video)
        .where(Video.user_id == current_user.id)
        .order_by(Video.created_at.desc())
    )
    videos = result.scalars().all()
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": current_user,
            "videos": videos
        }
    )


@router.get("/api/web/video-status/{video_id}", response_class=HTMLResponse)
async def get_video_status_badge(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """HTMX endpoint to poll video status and return updated badge"""
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        return '<span class="text-red-400">Not authenticated</span>'
    
    # Fetch video
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        return '<span class="text-red-400">Video not found</span>'
    
    # Return status badge HTML
    if video.status.value == 'completed':
        return f'''
        <div id="status-badge-{video.id}">
            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                </svg>
                Completed
            </span>
            <a href="/video/{video.id}" class="mt-4 block w-full text-center px-4 py-2 bg-primary hover:bg-primary/80 text-white rounded-lg transition-colors font-medium">
                View Transcript
            </a>
        </div>
        '''
    elif video.status.value == 'processing':
        return f'''
        <div id="status-badge-{video.id}" 
             hx-get="/api/web/video-status/{video.id}"
             hx-trigger="every 5s"
             hx-swap="outerHTML">
            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                <svg class="animate-spin w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing
            </span>
        </div>
        '''
    elif video.status.value == 'pending':
        return f'''
        <div id="status-badge-{video.id}"
             hx-get="/api/web/video-status/{video.id}"
             hx-trigger="every 5s"
             hx-swap="outerHTML">
            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"></path>
                </svg>
                Pending
            </span>
        </div>
        '''
    elif video.status.value == 'failed':
        return f'''
        <div id="status-badge-{video.id}">
            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                </svg>
                Failed
            </span>
        </div>
        '''
    
    return '<span class="text-gray-400">Unknown status</span>'



@router.post("/api/web/upload")
@limiter.limit("2/minute")  # Strict limit for upload endpoint
async def web_upload(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Web upload endpoint using cookie authentication with file hash deduplication"""
    from app.services.minio_service import MinIOService
    from app.models.database import VideoStatus
    from app.core.celery import process_video_task
    from app.core.config import settings
    import uuid
    
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    logger.info(f"Upload request from {current_user.email}: {file.filename}")  # nosec B608
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = "." + file.filename.split(".")[-1].lower()
    if file_ext not in settings.allowed_video_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file format: {file_ext}")
    
    # Read file content
    content = await file.read()
    
    # Calculate file hash for deduplication
    file_hash = calculate_file_hash(content)
    logger.info(f"Calculated file hash: {file_hash[:16]}... for {file.filename}")  # nosec B608
    
    # Check if this file already exists for this user
    result = await db.execute(
        select(Video).where(
            Video.user_id == current_user.id,
            Video.file_hash == file_hash
        )
    )
    existing_video = result.scalar_one_or_none()
    
    if existing_video:
        logger.info(f"Duplicate file detected: {file_hash[:16]}... - linking to existing video: {existing_video.id}")  # nosec B608
        return {
            "message": "This video has already been uploaded and processed",
            "video_id": str(existing_video.id),
            "duplicate": True,
            "status": existing_video.status.value
        }
    
    # Upload to MinIO
    minio_service = MinIOService()
    object_name = f"users/{current_user.id}/videos/{uuid.uuid4()}{file_ext}"
    minio_service.upload_file(content, object_name, file.content_type or "video/mp4")
    
    # Create video record with file hash
    video = Video(
        user_id=current_user.id,
        filename=file.filename,
        minio_object_key=object_name,
        file_hash=file_hash,
        status=VideoStatus.PENDING
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    
    # Submit Celery task
    task = process_video_task.delay(
        object_name,
        file.filename,
        str(current_user.id),
        str(video.id)
    )
    
    logger.info(f"Task submitted: {task.id} for video: {video.id}")  # nosec B608
    
    return {
        "message": "Upload successful",
        "task_id": task.id,
        "video_id": str(video.id),
        "duplicate": False
    }


@router.get("/api/web/videos/{video_id}/stream")
async def web_stream_video(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Web video streaming endpoint using cookie authentication"""
    from fastapi.responses import StreamingResponse
    from app.services.minio_service import MinIOService
    
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Fetch video
        result = await db.execute(
            select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
        )
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Stream video from MinIO
        minio_service = MinIOService()
        response = minio_service.client.get_object(minio_service.bucket_name, video.minio_object_key)
        
        return StreamingResponse(
            response.stream(),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{video.filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to stream video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to stream video")




@router.get("/api/web/chat/{video_id}/history", response_class=HTMLResponse)
async def get_chat_history(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get chat history for a video as HTML"""
    from app.models.database import ChatMessage
    import html
    
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        return ""
    
    # Fetch messages
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.video_id == video_id,
            ChatMessage.user_id == current_user.id
        )
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    
    # Build HTML with proper escaping
    html_parts = []
    for msg in messages:
        escaped_content = html.escape(msg.content)
        if msg.role == "user":
            html_parts.append(f'''
                <div class="flex justify-end">
                    <div class="bg-primary/20 border border-primary/30 rounded-lg px-4 py-2 max-w-xs">
                        <p class="text-sm text-white">{escaped_content}</p>
                    </div>
                </div>
            ''')
        else:
            html_parts.append(f'''
                <div class="flex justify-start">
                    <div class="bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 max-w-md">
                        <p class="text-sm text-gray-100">{escaped_content}</p>
                    </div>
                </div>
            ''')
    
    return "".join(html_parts)


@router.delete("/api/web/videos/{video_id}")
async def web_delete_video(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Web delete video endpoint using cookie authentication"""
    from app.services.minio_service import MinIOService
    
    try:
        current_user = await get_current_user_from_cookie(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    logger.info(f"Video deletion requested: {video_id} by user: {current_user.email}")
    
    # Fetch video
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        logger.warning(f"Video not found or access denied: {video_id}")
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete from MinIO
    try:
        minio_service = MinIOService()
        minio_service.delete_file(video.minio_object_key)
        logger.info(f"Deleted video from MinIO: {video.minio_object_key}")
    except Exception as e:
        logger.warning(f"Failed to delete from MinIO: {e}")
    
    # Delete from database (cascades to segments)
    await db.delete(video)
    await db.commit()
    
    logger.info(f"Video deleted successfully: {video_id}")
    return {"message": "Video deleted successfully", "video_id": video_id}

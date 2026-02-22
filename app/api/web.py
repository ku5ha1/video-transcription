from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password, create_access_token
from app.models.database import User, Video
from app.core.logging import get_logger

logger = get_logger("api.web")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
    except:
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
    
    logger.info(f"Video library accessed by {current_user.email}")
    
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

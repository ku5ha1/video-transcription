from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.models.database import User
from app.schemas.auth import UserRegister, Token, UserResponse
from app.core.logging import get_logger

logger = get_logger("api.auth")
router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user

    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 8 characters)
    """
    logger.info(f"Registration attempt for email: {user_data.email}")

    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Registration failed: Email already exists - {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    hashed_pwd = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed_pwd)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"User registered successfully: {new_user.id} ({new_user.email})")
    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """
    Login and receive JWT token

    OAuth2 compatible endpoint (use 'username' field for email)

    - **username**: User email address
    - **password**: User password

    Returns JWT access token for authentication
    """
    logger.info(f"Login attempt for email: {form_data.username}")

    # Fetch user by email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Login failed: Invalid credentials for {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Login failed: Inactive user - {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    # Create access token with user_id as subject
    access_token = create_access_token(data={"sub": str(user.id)})

    logger.info(f"User logged in successfully: {user.id} ({user.email})")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information

    Requires valid JWT token in Authorization header
    """
    logger.info(f"User info requested: {current_user.email}")
    return current_user

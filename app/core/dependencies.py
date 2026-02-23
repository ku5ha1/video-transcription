"""
FastAPI dependencies for authentication and authorization
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.database import User
from app.core.logging import get_logger

logger = get_logger("dependencies")

# OAuth2 scheme for token authentication
# tokenUrl points to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token

    This dependency:
    1. Extracts the JWT token from the Authorization header
    2. Decodes and validates the token
    3. Fetches the user from the database
    4. Validates the user is active

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        User object if authentication successful

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("Invalid or expired token")
        raise credentials_exception

    # Extract user_id from token payload
    user_id: str = payload.get("sub")
    if user_id is None:
        logger.warning("Token missing 'sub' claim")
        raise credentials_exception

    # Fetch user from database
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Database error while fetching user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    if user is None:
        logger.warning(f"User not found: {user_id}")
        raise credentials_exception

    if not user.is_active:
        logger.warning(f"Inactive user attempted access: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    logger.info(f"User authenticated successfully: {user.email}")
    return user

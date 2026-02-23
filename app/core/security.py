from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("security")

pwd_context = PasswordHash(
    (
        Argon2Hasher(
            time_cost=2,  # Number of iterations
            memory_cost=65536,  # Memory usage in KiB (64 MB)
            parallelism=4,  # Number of parallel threads
        ),
    )
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.jwt_expiration_days)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None

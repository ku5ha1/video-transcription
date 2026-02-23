from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.api import transcription, health, auth, chat, web
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, close_db
from app.core.redis_client import RedisClient
from app.services.vector_store import VectorStoreService

# Setup logging
setup_logging(settings.log_level)
logger = get_logger("main")

# Initialize rate limiter with Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["20/minute"],  # Global limit
    headers_enabled=True,
)

app = FastAPI(
    title="Video Transcription System",
    description="AI-powered video transcription with emotion and tone analysis",
    version="1.0.0",
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Initialize vector store service
vector_service = VectorStoreService()

# Include routers
app.include_router(web.router, tags=["web"])  # Web UI routes (no prefix)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(health.router, tags=["health"])


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Video Transcription API")
    # Initialize database (for development - use Alembic in production)
    if settings.debug:
        await init_db()
        logger.info("Database initialized")

    # Initialize Redis client
    await RedisClient.get_client()
    logger.info("Redis client initialized")

    # Initialize Qdrant collection
    vector_service.init_collection()
    logger.info("Qdrant collection initialized")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Video Transcription API")
    await close_db()
    await RedisClient.close()
    logger.info("Redis client closed")

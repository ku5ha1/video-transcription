from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import (
    SlowAPIMiddleware,
    sync_check_limits,
    _find_route_handler,
    _should_exempt,
)
from fastapi.responses import JSONResponse
from app.api import transcription, health, auth, chat, web
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, close_db
from app.core.redis_client import RedisClient
from app.services.vector_store import VectorStoreService

try:
    from redis.exceptions import ConnectionError as RedisConnectionError
except Exception:  # pragma: no cover - defensive import for test/runtime parity
    RedisConnectionError = ConnectionError

# Setup logging
setup_logging(settings.log_level)
logger = get_logger("main")


class SafeSlowAPIMiddleware(SlowAPIMiddleware):
    """Guard against missing view_rate_limit when backend errors are swallowed."""

    async def dispatch(self, request, call_next):
        app = request.app
        limiter = app.state.limiter

        if not limiter.enabled:
            return await call_next(request)

        handler = _find_route_handler(app.routes, request.scope)
        if _should_exempt(limiter, handler):
            return await call_next(request)

        error_response, should_inject_headers = sync_check_limits(
            limiter, request, handler, app
        )
        if error_response is not None:
            return error_response

        response = await call_next(request)
        if should_inject_headers and hasattr(request.state, "view_rate_limit"):
            response = limiter._inject_headers(response, request.state.view_rate_limit)
        return response


# Initialize rate limiter with Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["20/minute"],  # Global limit
    headers_enabled=False,
    swallow_errors=True,
)

app = FastAPI(
    title="Video Transcription System",
    description="AI-powered video transcription with emotion and tone analysis",
    version="1.0.0",
)


def rate_limit_exception_handler(request, exc):
    """
    SlowAPI can surface backend/storage errors (e.g., Redis connection issues)
    through the same exception hook used for rate-limit violations.
    Handle both explicitly so infra hiccups do not crash requests with AttributeError.
    """
    if isinstance(exc, RateLimitExceeded):
        return _rate_limit_exceeded_handler(request, exc)

    logger.error(f"Rate limiter backend error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"error": "Rate limiter backend unavailable"},
    )


# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_exception_handler(ConnectionError, rate_limit_exception_handler)
if RedisConnectionError is not ConnectionError:
    app.add_exception_handler(RedisConnectionError, rate_limit_exception_handler)
app.add_middleware(SafeSlowAPIMiddleware)

# Initialize vector store service lazily during startup
vector_service = None

# Include routers
app.include_router(web.router, tags=["web"])  # Web UI routes (no prefix)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(health.router, tags=["health"])


@app.on_event("startup")
async def startup_event():
    global vector_service
    logger.info("Starting Video Transcription API")
    # Initialize database (for development - use Alembic in production)
    if settings.debug:
        await init_db()
        logger.info("Database initialized")

    # Initialize Redis client
    await RedisClient.get_client()
    logger.info("Redis client initialized")

    # Initialize Qdrant collection
    try:
        vector_service = VectorStoreService()
        if vector_service.init_collection():
            logger.info("Qdrant collection initialized")
        else:
            logger.warning("Qdrant collection initialization failed")
    except Exception as e:
        logger.warning(f"Vector store initialization skipped: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Video Transcription API")
    await close_db()
    await RedisClient.close()
    logger.info("Redis client closed")

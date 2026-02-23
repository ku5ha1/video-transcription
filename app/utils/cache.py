"""
Caching utilities for Redis-based response caching
"""

import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
from app.core.redis_client import get_redis
from app.core.logging import get_logger

logger = get_logger("utils.cache")

# Cache key prefixes
CACHE_PREFIX_TRANSCRIPT = "cache:transcript:"
CACHE_PREFIX_CHAT = "cache:chat:"
CACHE_PREFIX_VIDEO_HASH = "hash:video:"

# Default TTLs (in seconds)
TTL_TRANSCRIPT = 3600  # 1 hour
TTL_CHAT = 7200  # 2 hours
TTL_VIDEO_HASH = 86400 * 30  # 30 days


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a cache key from prefix and arguments

    Args:
        prefix: Cache key prefix
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        Cache key string
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    key_data = ":".join(key_parts)
    return f"{prefix}{key_data}"


def generate_query_hash(query: str) -> str:
    """
    Generate SHA-256 hash of a query string

    Args:
        query: Query string to hash

    Returns:
        Hex digest of hash
    """
    return hashlib.sha256(query.encode()).hexdigest()


async def get_cached_value(key: str) -> Optional[Any]:
    """
    Get cached value from Redis

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found
    """
    try:
        redis = await get_redis()
        value = await redis.get(key)
        if value:
            logger.debug(f"Cache hit: {key}")
            return json.loads(value)
        logger.debug(f"Cache miss: {key}")
        return None
    except Exception as e:
        logger.error(f"Failed to get cached value for {key}: {e}")
        return None


async def set_cached_value(key: str, value: Any, ttl: int = 3600) -> bool:
    """
    Set cached value in Redis with TTL

    Args:
        key: Cache key
        value: Value to cache (must be JSON serializable)
        ttl: Time to live in seconds

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis()
        serialized = json.dumps(value)
        await redis.setex(key, ttl, serialized)
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Failed to set cached value for {key}: {e}")
        return False


async def delete_cached_value(key: str) -> bool:
    """
    Delete cached value from Redis

    Args:
        key: Cache key

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis()
        await redis.delete(key)
        logger.debug(f"Cache deleted: {key}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete cached value for {key}: {e}")
        return False


async def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern

    Args:
        pattern: Redis key pattern (e.g., "cache:transcript:*")

    Returns:
        Number of keys deleted
    """
    try:
        redis = await get_redis()
        keys = []
        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            deleted = await redis.delete(*keys)
            logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")
            return deleted
        return 0
    except Exception as e:
        logger.error(f"Failed to invalidate pattern {pattern}: {e}")
        return 0


def cache_response(
    prefix: str, ttl: int = 3600, key_builder: Optional[Callable] = None
):
    """
    Decorator for caching function responses in Redis

    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_builder: Optional custom function to build cache key from args

    Usage:
        @cache_response("cache:transcript:", ttl=3600)
        async def get_transcript(video_id: str):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = generate_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached = await get_cached_value(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await set_cached_value(cache_key, result, ttl)

            return result

        return wrapper

    return decorator

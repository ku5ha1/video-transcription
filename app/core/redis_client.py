"""
Redis client for caching and rate limiting
"""
import redis.asyncio as aioredis
from redis.asyncio import Redis
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("redis_client")

class RedisClient:
    """Singleton Redis client for application-wide caching"""
    
    _instance: Optional[Redis] = None
    
    @classmethod
    async def get_client(cls) -> Redis:
        """Get or create Redis client instance"""
        if cls._instance is None:
            try:
                cls._instance = await aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=10
                )
                logger.info("Redis client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {e}")
                raise
        return cls._instance
    
    @classmethod
    async def close(cls):
        """Close Redis connection"""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Redis client closed")

# Global instance getter
async def get_redis() -> Redis:
    """Dependency for getting Redis client"""
    return await RedisClient.get_client()

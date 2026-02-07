from fastapi import APIRouter, HTTPException
from app.core.logging import get_logger
from app.core.config import settings
import redis
from minio import Minio
from minio.error import S3Error
import httpx
from celery import Celery
from typing import Dict, Any

logger = get_logger("api.health")
router = APIRouter()

def check_redis() -> Dict[str, Any]:
    """Check Redis connection"""
    try:
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        return {"status": "healthy", "message": "Redis is reachable"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}

def check_minio() -> Dict[str, Any]:
    """Check MinIO connection"""
    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        # Try to list buckets as a health check
        list(client.list_buckets())
        return {"status": "healthy", "message": "MinIO is reachable"}
    except S3Error as e:
        logger.error(f"MinIO health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}
    except Exception as e:
        logger.error(f"MinIO health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}

def check_qdrant() -> Dict[str, Any]:
    """Check Qdrant connection"""
    try:
        import httpx
        response = httpx.get(f"{settings.qdrant_url}/health", timeout=2.0)
        if response.status_code == 200:
            return {"status": "healthy", "message": "Qdrant is reachable"}
        else:
            return {"status": "unhealthy", "message": f"Status code: {response.status_code}"}
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}

def check_celery() -> Dict[str, Any]:
    """Check Celery worker status"""
    try:
        celery_app = Celery(broker=settings.redis_url, backend=settings.redis_url)
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            worker_count = len(active_workers)
            return {
                "status": "healthy", 
                "message": f"{worker_count} worker(s) active",
                "workers": list(active_workers.keys())
            }
        else:
            return {"status": "unhealthy", "message": "No active workers found"}
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check for all services"""
    logger.info("Detailed health check requested")
    
    health_status = {
        "service": settings.app_name,
        "version": "1.0.0",
        "components": {
            "redis": check_redis(),
            "minio": check_minio(),
            "qdrant": check_qdrant(),
            "celery": check_celery()
        }
    }
    
    # Determine overall status
    all_healthy = all(
        component["status"] == "healthy" 
        for component in health_status["components"].values()
    )
    
    health_status["status"] = "healthy" if all_healthy else "degraded"
    
    logger.info(f"Health check completed: {health_status['status']}")
    
    # Return 503 if any component is unhealthy
    if not all_healthy:
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@router.get("/health/ready")
async def readiness_check():
    """Kubernetes-style readiness probe"""
    redis_status = check_redis()
    
    if redis_status["status"] == "healthy":
        return {"ready": True, "message": "Service is ready"}
    else:
        raise HTTPException(status_code=503, detail={"ready": False, "message": "Service not ready"})
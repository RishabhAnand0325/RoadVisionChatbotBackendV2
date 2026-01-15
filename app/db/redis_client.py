"""
Reusable Redis client for the application.
"""
import redis
from app.config import settings

def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client instance connected to the configured Redis server.
    """
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True  # Decode responses to strings by default
    )

# A singleton instance for reuse across the application
redis_client = get_redis_client()

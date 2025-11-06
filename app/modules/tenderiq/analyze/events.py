"""
Handles publishing of real-time analysis events to Redis Pub/Sub.
"""
import json
from uuid import UUID
from app.db.redis_client import redis_client

def get_analysis_channel(analysis_id: UUID) -> str:
    """Returns the Redis channel name for a specific analysis."""
    return f"analysis:{analysis_id}"

def publish_update(analysis_id: UUID, field: str, data: any, event_type: str = "update"):
    """
    Publishes an update to the analysis-specific Redis channel.
    """
    channel = get_analysis_channel(analysis_id)
    message = {
        "event": event_type,
        "field": field,
        "data": data,
    }
    redis_client.publish(channel, json.dumps(message))

"""
Service to orchestrate the real-time analysis SSE stream.
"""
import json
import asyncio
from uuid import UUID
from fastapi import Request
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.orm import Session

from app.db.redis_client import redis_client
from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.db.schema import TenderAnalysis, AnalysisStatusEnum
from app.modules.tenderiq.analyze.tasks import run_tender_analysis
from app.modules.tenderiq.analyze.events import get_analysis_channel

class AnalysisOrchestratorService:
    """Manages the SSE connection and analysis lifecycle."""

    def __init__(self, db: Session):
        self.db = db
        self.analyze_repo = AnalyzeRepository(db)

    async def stream_analysis(self, tender_id: UUID, user_id: UUID, request: Request):
        """
        Handles the SSE connection for a tender analysis.
        """
        analysis = self.analyze_repo.get_by_tender_id(tender_id)

        if not analysis:
            # First request: create analysis record and trigger background task
            analysis = self.analyze_repo.create_for_tender(tender_id, user_id)
            run_tender_analysis.delay(str(analysis.id))
        
        return EventSourceResponse(self._stream_generator(analysis, request))

    async def _stream_generator(self, analysis: TenderAnalysis, request: Request):
        """A generator function that yields SSE events."""
        
        # 1. Immediately send the current state from the database
        yield self._format_sse_event("initial_state", "full", analysis.to_dict()) # Assumes a to_dict method

        # 2. If analysis is already complete or failed, close the connection
        if analysis.status in [AnalysisStatusEnum.completed, AnalysisStatusEnum.failed]:
            yield self._format_sse_event("control", "close", "Analysis already finished.")
            return

        # 3. Subscribe to Redis for live updates
        pubsub = redis_client.pubsub()
        channel = get_analysis_channel(analysis.id)
        await pubsub.subscribe(channel)

        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    event_data = json.loads(message['data'])
                    yield ServerSentEvent(data=json.dumps(event_data), event=event_data.get("event"))

                    # Check for a 'close' control message from the backend
                    if event_data.get("event") == "control" and event_data.get("data") == "close":
                        break
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)

    def _format_sse_event(self, event_name: str, field_name: str, data: any) -> ServerSentEvent:
        """Helper to format data into an SSE-compatible event."""
        return ServerSentEvent(data=json.dumps({"event": event_name, "field": field_name, "data": data}), event=event_name)

from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class SummaryCard(BaseModel):
    title: str
    metric: str
    description: Optional[str] = None

class ActivityItem(BaseModel):
    id: UUID
    user_id: UUID
    action_type: str
    action_details: dict
    timestamp: datetime

class DashboardData(BaseModel):
    summary_cards: List[SummaryCard]
    recent_activity: List[ActivityItem]

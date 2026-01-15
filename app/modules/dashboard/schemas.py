from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PlatformSummary(BaseModel):
    activeUsers: int
    activeUsersTrend: int
    aiQueriesToday: int
    aiQueriesTodayTrend: int
    tendersAnalyzed: int
    activeCases: int

class RecentActivity(BaseModel):
    id: str
    type: str
    title: str
    module: str
    timestamp: datetime
    status: str
    icon: str

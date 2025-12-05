from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.database import get_db_session
from app.modules.dashboard.schemas import PlatformSummary, RecentActivity
from app.modules.auth.db.schema import User
from app.modules.askai.db.models import Chat
from app.modules.scraper.db.schema import ScrapedTender
from app.modules.legaliq.db.schema import Case, ActivityLog

router = APIRouter()

@router.get("/summary", response_model=PlatformSummary)
def get_dashboard_summary(db: Session = Depends(get_db_session)):
    # Active Users
    active_users = db.query(User).filter(User.account_status == 'Active').count()
    
    # AI Queries Today
    today = datetime.utcnow().date()
    ai_queries_today = db.query(Chat).filter(func.date(Chat.created_at) == today).count()
    
    # Tenders Analyzed (This Month)
    # ScrapedTender doesn't have created_at, so we join with ScrapeRun via ScrapedTenderQuery
    from app.modules.scraper.db.schema import ScrapedTenderQuery, ScrapeRun
    
    first_day_this_month = today.replace(day=1)
    tenders_analyzed = (
        db.query(ScrapedTender)
        .join(ScrapedTender.query)
        .join(ScrapedTenderQuery.scrape_run)
        .filter(func.date(ScrapeRun.run_at) >= first_day_this_month)
        .count()
    )
    
    # Active Cases
    active_cases = db.query(Case).filter(Case.status.notin_(['Closed', 'Archived'])).count()
    
    return PlatformSummary(
        activeUsers=active_users,
        activeUsersTrend=12, # Mocked trend
        aiQueriesToday=ai_queries_today,
        aiQueriesTodayTrend=8, # Mocked trend
        tendersAnalyzed=tenders_analyzed,
        activeCases=active_cases
    )

@router.get("/activity/recent", response_model=List[RecentActivity])
def get_recent_activity(db: Session = Depends(get_db_session)):
    activities = []
    
    # Recent Chats
    recent_chats = db.query(Chat).order_by(desc(Chat.created_at)).limit(5).all()
    for chat in recent_chats:
        activities.append(RecentActivity(
            id=str(chat.id),
            type="chat",
            title=chat.title,
            module="Ask CeigallAI",
            timestamp=chat.created_at,
            status="complete",
            icon="MessageSquare"
        ))
        
    # Recent LegalIQ Activity
    recent_logs = db.query(ActivityLog).order_by(desc(ActivityLog.timestamp)).limit(5).all()
    for log in recent_logs:
        activities.append(RecentActivity(
            id=str(log.id),
            type="log",
            title=f"{log.action_type}: {log.action_details.get('description', '') if log.action_details else ''}",
            module="LegalIQ",
            timestamp=log.timestamp,
            status="complete",
            icon="Briefcase"
        ))
    
    # Sort by timestamp descending and take top 10
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    return activities[:10]

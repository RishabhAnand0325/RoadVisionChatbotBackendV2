"""
Celery tasks for automated tender corrigendum detection and tracking.

This module contains background tasks that periodically check for 
corrigendums and amendments to active tenders.
"""

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID
import logging

from app.celery_app import celery_app
from app.db.database import SessionLocal
from app.modules.tenderiq.db.schema import Tender
from app.modules.tenderiq.services.corrigendum_service import CorrigendumTrackingService
from app.modules.scraper.db.schema import ScrapedTender

logger = logging.getLogger(__name__)


@celery_app.task(name="check_active_tenders_for_corrigendums")
def check_active_tenders_for_corrigendums():
    """
    Periodic task to check all active tenders for corrigendums.
    
    This task:
    1. Identifies tenders with upcoming deadlines (within next 30 days)
    2. Re-scrapes tender data from source portals
    3. Detects changes and logs them as corrigendums
    
    Schedule: Should run every 6-12 hours via Celery Beat
    """
    db = SessionLocal()
    try:
        logger.info("Starting corrigendum check for active tenders...")
        
        # Get active tenders (upcoming deadlines within next 30 days)
        cutoff_date = datetime.now(timezone.utc) + timedelta(days=30)
        active_tenders = db.query(Tender).filter(
            Tender.submission_deadline > datetime.now(timezone.utc),
            Tender.submission_deadline < cutoff_date,
            Tender.status.in_(['New', 'Reviewed', 'Shortlisted', 'Bid_Preparation'])
        ).all()
        
        logger.info(f"Found {len(active_tenders)} active tenders to check")
        
        corrigendum_service = CorrigendumTrackingService(db)
        corrigendums_found = 0
        
        for tender in active_tenders:
            try:
                # Get latest scraped data for this tender
                latest_scraped = db.query(ScrapedTender).filter(
                    ScrapedTender.tender_id_str == tender.tender_ref_number
                ).order_by(ScrapedTender.scraped_at.desc()).first()
                
                if not latest_scraped:
                    logger.warning(f"No scraped data found for tender {tender.tender_ref_number}")
                    continue
                
                # TODO: Implement re-scraping logic here
                # For now, we'll use the existing latest scraped data
                # In production, you would trigger a re-scrape of the tender portal
                
                # Detect changes
                changes = corrigendum_service.detect_changes(
                    tender.tender_ref_number,
                    latest_scraped
                )
                
                if changes:
                    logger.info(f"Corrigendum detected for tender {tender.tender_ref_number}: {len(changes)} changes")
                    
                    # TODO: Auto-apply changes or flag for review?
                    # For now, we'll just log them
                    # You could add: corrigendum_service.apply_corrigendum(...)
                    
                    corrigendums_found += 1
                    
            except Exception as e:
                logger.error(f"Error checking tender {tender.tender_ref_number}: {str(e)}")
                continue
        
        logger.info(f"Corrigendum check complete. Found {corrigendums_found} tenders with changes")
        return {
            "status": "success",
            "tenders_checked": len(active_tenders),
            "corrigendums_found": corrigendums_found
        }
        
    except Exception as e:
        logger.error(f"Error in corrigendum check task: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()


@celery_app.task(name="check_single_tender_for_corrigendum")
def check_single_tender_for_corrigendum(tender_id: str):
    """
    Check a specific tender for corrigendums.
    
    Args:
        tender_id: Tender reference number or UUID
        
    This can be triggered manually or by webhook from scraper.
    """
    db = SessionLocal()
    try:
        logger.info(f"Checking tender {tender_id} for corrigendum...")
        
        corrigendum_service = CorrigendumTrackingService(db)
        
        # Try to parse as UUID, otherwise treat as tender_ref_number
        try:
            tender_uuid = UUID(tender_id)
            tender = db.query(Tender).filter(Tender.id == tender_uuid).first()
        except ValueError:
            tender = db.query(Tender).filter(Tender.tender_ref_number == tender_id).first()
        
        if not tender:
            logger.error(f"Tender {tender_id} not found")
            return {"status": "error", "error": "Tender not found"}
        
        # Get latest scraped data
        latest_scraped = db.query(ScrapedTender).filter(
            ScrapedTender.tender_id_str == tender.tender_ref_number
        ).order_by(ScrapedTender.scraped_at.desc()).first()
        
        if not latest_scraped:
            return {"status": "error", "error": "No scraped data found"}
        
        # Detect changes
        changes = corrigendum_service.detect_changes(
            tender.tender_ref_number,
            latest_scraped
        )
        
        if changes:
            logger.info(f"Found {len(changes)} changes for tender {tender.tender_ref_number}")
            return {
                "status": "success",
                "changes_found": len(changes),
                "changes": [
                    {
                        "field": change.field,
                        "old_value": str(change.old_value),
                        "new_value": str(change.new_value)
                    }
                    for change in changes
                ]
            }
        else:
            return {"status": "success", "changes_found": 0}
            
    except Exception as e:
        logger.error(f"Error checking tender {tender_id}: {str(e)}")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


# Configure Celery Beat schedule
# Add this to your celery configuration to enable periodic checks
"""
celery_app.conf.beat_schedule = {
    'check-corrigendums-every-6-hours': {
        'task': 'check_active_tenders_for_corrigendums',
        'schedule': timedelta(hours=6),
    },
}
"""

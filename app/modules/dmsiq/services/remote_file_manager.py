"""
Remote File Manager for DMS Module.

Implements the "blackbox" abstraction that hides whether files are stored locally or remotely.
Handles:
- Retrieving files from internet URLs
- Caching files locally on-demand
- Tracking cache status in database
- Serving both local and remote files transparently to consumers

This enables the hybrid storage strategy where files remain on the internet by default
but can be cached locally for faster access.
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.modules.dmsiq.services.file_storage import FileStorageService, DMS_ROOT
from app.modules.scraper.db.schema import ScrapedTenderFile
from app.modules.scraper.db.repository import ScraperRepository


class RemoteFileManager:
    """
    Manages both remote and cached files transparently.

    Usage:
    - get_file(): Returns bytes of file (fetches from internet or local cache)
    - cache_file_async(): Register file for background caching
    - get_file_path(): Returns DMS path whether file is cached or not
    """

    def __init__(self, db: Session):
        """
        Initialize RemoteFileManager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.scraper_repo = ScraperRepository(db)

    def get_file(self, file_id: str) -> Tuple[bool, Optional[bytes], dict]:
        """
        Get file content from either local cache or remote location.
        Acts as transparent layer - caller doesn't care where file comes from.

        Args:
            file_id: UUID of ScrapedTenderFile

        Returns:
            Tuple of (success, file_content, metadata)
            metadata includes: source (local/remote), timestamp, size, etc.
        """
        # Get file record from database
        file_record = self.db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.id == file_id
        ).first()

        if not file_record:
            return False, None, {"error": "File not found in database"}

        metadata = {
            "file_name": file_record.file_name,
            "file_size": file_record.file_size,
            "cache_status": file_record.cache_status,
        }

        # Check if file is cached locally
        if file_record.is_cached and file_record.dms_path:
            success, content = FileStorageService.read_file(file_record.dms_path)
            if success:
                metadata["source"] = "local_cache"
                metadata["timestamp"] = datetime.now().isoformat()
                return True, content, metadata

        # File not cached, fetch from remote URL
        if not file_record.file_url:
            return False, None, {"error": "No file URL or cached copy available"}

        try:
            response = requests.get(file_record.file_url, timeout=30)
            response.raise_for_status()

            metadata["source"] = "remote"
            metadata["timestamp"] = datetime.now().isoformat()

            return True, response.content, metadata

        except requests.RequestException as e:
            return False, None, {"error": f"Failed to fetch remote file: {str(e)}"}

    def get_file_path(self, file_id: str) -> Tuple[bool, Optional[str]]:
        """
        Get the file path (DMS reference path).
        If file is cached locally, returns local path. Otherwise returns DMS path reference.

        Args:
            file_id: UUID of ScrapedTenderFile

        Returns:
            Tuple of (success, file_path)
        """
        file_record = self.db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.id == file_id
        ).first()

        if not file_record:
            return False, None

        # Always return DMS path (whether cached or not)
        # DMS path format: /tenders/YYYY/MM/DD/tender_id/files/filename
        return True, file_record.dms_path

    def cache_file_async(self, file_id: str) -> Tuple[bool, str]:
        """
        Register a file for background caching.
        In production, this would queue a background job to download and cache the file.

        For MVP: Can be called manually or by a background worker.

        Args:
            file_id: UUID of ScrapedTenderFile

        Returns:
            Tuple of (success, message)
        """
        file_record = self.db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.id == file_id
        ).first()

        if not file_record:
            return False, "File not found"

        # If already cached, nothing to do
        if file_record.is_cached:
            return True, "File already cached"

        # If no URL, can't cache
        if not file_record.file_url:
            return False, "No remote URL to cache from"

        # Download and cache the file
        return self.cache_file_sync(file_record)

    def cache_file_sync(self, file_record: ScrapedTenderFile) -> Tuple[bool, str]:
        """
        Synchronously download and cache a file.
        Updates database with cache status.

        Args:
            file_record: ScrapedTenderFile database record

        Returns:
            Tuple of (success, message)
        """
        try:
            # Download file from remote
            response = requests.get(file_record.file_url, timeout=60)
            response.raise_for_status()

            # Save to local DMS storage
            success, result = FileStorageService.save_file(
                response.content,
                file_record.dms_path
            )

            if not success:
                # Update database with failure
                file_record.cache_status = "failed"
                file_record.cache_error = result
                self.db.commit()
                return False, f"Failed to save file: {result}"

            # Update database with success
            file_record.is_cached = True
            file_record.cache_status = "cached"
            file_record.cache_error = None
            self.db.commit()

            return True, f"File cached successfully: {result}"

        except requests.RequestException as e:
            # Update database with failure
            file_record.cache_status = "failed"
            file_record.cache_error = f"Download failed: {str(e)}"
            self.db.commit()
            return False, f"Failed to download file: {str(e)}"

        except Exception as e:
            # Update database with failure
            file_record.cache_status = "failed"
            file_record.cache_error = f"Unexpected error: {str(e)}"
            self.db.commit()
            return False, f"Unexpected error: {str(e)}"

    def bulk_cache_files(self, tender_id: str, priority: str = "normal") -> Tuple[int, int]:
        """
        Cache all files for a specific tender.
        Useful for pre-caching tenders from specific dates.

        Args:
            tender_id: UUID of ScrapedTender
            priority: For future queue management (normal, high)

        Returns:
            Tuple of (cached_count, failed_count)
        """
        files = self.db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.tender_id == tender_id,
            ScrapedTenderFile.is_cached == False
        ).all()

        cached_count = 0
        failed_count = 0

        for file_record in files:
            success, _ = self.cache_file_sync(file_record)
            if success:
                cached_count += 1
            else:
                failed_count += 1

        return cached_count, failed_count

    def get_cache_status(self, tender_id: str) -> dict:
        """
        Get caching status for all files in a tender.

        Args:
            tender_id: UUID of ScrapedTender

        Returns:
            Dictionary with cache statistics
        """
        files = self.db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.tender_id == tender_id
        ).all()

        total = len(files)
        cached = sum(1 for f in files if f.is_cached)
        pending = sum(1 for f in files if f.cache_status == "pending")
        failed = sum(1 for f in files if f.cache_status == "failed")

        return {
            "total_files": total,
            "cached_files": cached,
            "pending_files": pending,
            "failed_files": failed,
            "cache_percentage": (cached / total * 100) if total > 0 else 0,
        }

    def get_uncached_files(self, limit: int = 100) -> list[ScrapedTenderFile]:
        """
        Get list of uncached files that can be cached (for background job).

        Args:
            limit: Maximum number of files to return

        Returns:
            List of ScrapedTenderFile records with pending status
        """
        return self.db.query(ScrapedTenderFile).filter(
            ScrapedTenderFile.is_cached == False,
            ScrapedTenderFile.cache_status == "pending"
        ).limit(limit).all()

    def generate_dms_path(self, tender_id: str, filename: str, tender_release_date: str) -> str:
        """
        Generate DMS path for a file based on tender and date.

        Format: /tenders/YYYY/MM/DD/[tender_id]/files/[filename]

        Args:
            tender_id: UUID of tender
            filename: Original filename
            tender_release_date: Date string in format YYYY-MM-DD

        Returns:
            DMS path string
        """
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)

        # Parse date
        year, month, day = tender_release_date.split('-')

        # Construct path
        dms_path = f"/tenders/{year}/{month}/{day}/{tender_id}/files/{safe_filename}"
        return dms_path

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Remove special characters from filename while preserving extension."""
        name, ext = os.path.splitext(filename)
        # Keep only alphanumeric, hyphens, underscores
        name = re.sub(r'[^\w\-]', '', name)
        return f"{name}{ext}" if ext else name

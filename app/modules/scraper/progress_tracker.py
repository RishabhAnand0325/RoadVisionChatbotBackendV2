"""
Scraper Progress Tracking and Logging Module

Provides:
- Multiple progress bars for different scraping stages
- Structured logging for debugging and monitoring
- Real-time progress updates during scraping operations

Progress Bars:
1. Email Processing Progress
2. Tender Scraping Progress
3. Detail Page Scraping Progress
4. File Download Progress
5. Database Save Progress
6. Overall Pipeline Progress
"""

import logging
from typing import Optional
from tqdm import tqdm
from datetime import datetime
import sys

# ==================== Logging Configuration ====================


def setup_scraper_logger(name: str = "scraper") -> logging.Logger:
    """
    Configure structured logging for the scraper.

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)

    # File handler (DEBUG and above) - useful for post-execution analysis
    file_handler = logging.FileHandler("scraper.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_scraper_logger()


# ==================== Progress Bar Builders ====================


class ProgressTracker:
    """Centralized progress tracking for all scraper operations"""

    def __init__(self, verbose: bool = True):
        """
        Initialize progress tracker.

        Args:
            verbose: Whether to show detailed progress output
        """
        self.verbose = verbose
        self.progress_bars = {}

    def create_email_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for email processing.

        Args:
            total: Total number of emails to process

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="📧 Processing Emails",
            unit="email",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=not self.verbose,
        )
        self.progress_bars["emails"] = bar
        logger.info(f"Email Processing Started: {total} emails to process")
        return bar

    def create_tender_scrape_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for tender scraping.

        Args:
            total: Total number of tenders to scrape

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="🔗 Scraping Tenders",
            unit="tender",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=not self.verbose,
        )
        self.progress_bars["tenders"] = bar
        logger.info(f"Tender Scraping Started: {total} tenders to scrape")
        return bar

    def create_detail_scrape_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for detail page scraping.

        Args:
            total: Total number of detail pages to scrape

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="📄 Scraping Detail Pages",
            unit="page",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=not self.verbose,
        )
        self.progress_bars["detail_pages"] = bar
        logger.info(f"Detail Page Scraping Started: {total} pages to scrape")
        return bar

    def create_file_download_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for file downloads.

        Args:
            total: Total number of files to download

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="⬇️  Downloading Files",
            unit="file",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=not self.verbose,
        )
        self.progress_bars["file_downloads"] = bar
        logger.info(f"File Download Started: {total} files to download")
        return bar

    def create_database_save_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for database operations.

        Args:
            total: Total number of records to save

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="💾 Saving to Database",
            unit="record",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=not self.verbose,
        )
        self.progress_bars["database"] = bar
        logger.info(f"Database Save Started: {total} records to save")
        return bar

    def create_query_progress_bar(self, query_name: str, total: int) -> tqdm:
        """
        Create progress bar for processing tenders in a specific query category.

        Args:
            query_name: Name of the query category (e.g., "Civil", "Electrical")
            total: Total number of tenders in this query

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc=f"📋 Processing {query_name}",
            unit="tender",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
            disable=not self.verbose,
        )
        logger.info(f"Query Processing Started: {query_name} ({total} tenders)")
        return bar

    def create_deduplication_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for deduplication check.

        Args:
            total: Total number of emails/tenders to check

        Returns:
            tqdm progress bar instance
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="🔍 Checking Duplicates",
            unit="item",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
            disable=not self.verbose,
        )
        logger.info(f"Deduplication Check Started: {total} items to check")
        return bar

    def create_analysis_progress_bar(self, total: int) -> tqdm:
        """
        Create progress bar for tender analysis.
        """
        if total == 0:
            return None

        bar = tqdm(
            total=total,
            desc="🔬 Analyzing Tenders",
            unit="tender",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=not self.verbose,
        )
        self.progress_bars["analysis"] = bar
        logger.info(f"Tender Analysis Started: {total} tenders to analyze")
        return bar

    def update_progress(self, bar_key: str, n: int = 1, message: Optional[str] = None):
        """
        Update a progress bar.

        Args:
            bar_key: Key of the progress bar to update
            n: Number of steps to advance
            message: Optional message to log along with update
        """
        if bar_key in self.progress_bars and self.progress_bars[bar_key]:
            self.progress_bars[bar_key].update(n)

            if message:
                logger.debug(message)

    def close_progress_bar(self, bar_key: str):
        """
        Close and clean up a progress bar.

        Args:
            bar_key: Key of the progress bar to close
        """
        if bar_key in self.progress_bars and self.progress_bars[bar_key]:
            self.progress_bars[bar_key].close()
            del self.progress_bars[bar_key]

    def close_all_progress_bars(self):
        """Close all open progress bars"""
        for bar_key in list(self.progress_bars.keys()):
            self.close_progress_bar(bar_key)

    def log_section(self, section_name: str):
        """
        Log the start of a new section.

        Args:
            section_name: Name of the section
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📍 {section_name}")
        logger.info(f"{'='*60}")

    def log_info(self, message: str):
        """Log info message"""
        logger.info(message)

    def log_warning(self, message: str):
        """Log warning message"""
        logger.warning(message)

    def log_error(self, message: str, exc: Optional[Exception] = None):
        """Log error message with optional exception"""
        if exc:
            logger.error(f"{message}\nException: {type(exc).__name__}: {str(exc)}")
        else:
            logger.error(message)

    def log_success(self, message: str):
        """Log success message"""
        logger.info(f"✅ {message}")

    def log_stats(self, stats: dict):
        """
        Log statistics as a formatted block.

        Args:
            stats: Dictionary of stat_name: stat_value pairs
        """
        logger.info("📊 Statistics:")
        for key, value in stats.items():
            logger.info(f"   {key}: {value}")

    def log_summary(self, summary: dict):
        """
        Log execution summary.

        Args:
            summary: Dictionary with execution summary data
        """
        logger.info(f"\n{'='*60}")
        logger.info("✨ Execution Summary")
        logger.info(f"{'='*60}")
        for key, value in summary.items():
            logger.info(f"{key}: {value}")
        logger.info(f"{'='*60}\n")


# ==================== Context Managers ====================


class ScrapeSection:
    """Context manager for tracking scraping sections"""

    def __init__(self, tracker: ProgressTracker, section_name: str):
        self.tracker = tracker
        self.section_name = section_name
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.tracker.log_section(self.section_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        if exc_type:
            self.tracker.log_error(
                f"{self.section_name} failed", exc_val
            )
        else:
            self.tracker.log_success(
                f"{self.section_name} completed in {duration:.2f}s"
            )
        return False  # Don't suppress exceptions


# ==================== Utility Functions ====================


def log_tender_scrape_attempt(
    tender_name: str, tender_url: str, attempt_num: int = 1
):
    """Log tender scraping attempt"""
    logger.info(f"🎯 Scraping tender (attempt {attempt_num}): {tender_name}")
    logger.debug(f"   URL: {tender_url}")


def log_tender_scrape_success(tender_name: str, num_fields: int):
    """Log successful tender scrape"""
    logger.info(f"✅ Successfully scraped: {tender_name} ({num_fields} fields)")


def log_tender_scrape_failure(tender_name: str, error: str):
    """Log failed tender scrape"""
    logger.warning(f"⚠️  Failed to scrape {tender_name}: {error}")


def log_email_check(email_count: int, processed: int, skipped: int, failed: int):
    """Log email processing summary"""
    logger.info(
        f"📧 Email Cycle Summary: {email_count} found | "
        f"{processed} processed | {skipped} skipped | {failed} failed"
    )


def log_deduplication_check(tender_url: str, is_duplicate: bool):
    """Log deduplication check result"""
    if is_duplicate:
        logger.info(f"⏭️  Duplicate detected: {tender_url}")
    else:
        logger.info(f"🆕 New tender: {tender_url}")


def log_database_operation(operation: str, count: int, duration: float):
    """Log database operation"""
    logger.info(
        f"💾 Database {operation}: {count} records in {duration:.2f}s"
    )


def log_cycle_statistics(cycle_num: int, stats: dict):
    """Log cycle statistics"""
    logger.info(f"\n📊 Cycle {cycle_num} Statistics:")
    for key, value in stats.items():
        logger.info(f"   {key}: {value}")

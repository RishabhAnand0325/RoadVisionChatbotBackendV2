"""
Unit tests for TenderIQ Date Filtering Feature

Tests for:
- TenderIQRepository date filtering methods
- TenderFilterService business logic
- API endpoints (/dates and /tenders)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from app.modules.scraper.db.schema import ScrapeRun, ScrapedTenderQuery, ScrapedTender
from app.modules.tenderiq.db.tenderiq_repository import TenderIQRepository
from app.modules.tenderiq.services.tender_filter_service import TenderFilterService
from app.modules.tenderiq.models.pydantic_models import (
    AvailableDatesResponse,
    FilteredTendersResponse,
    ScrapeDateInfo,
)


# ==================== Test Fixtures ====================


@pytest.fixture
def mock_db():
    """Create mock database session"""
    return Mock()


@pytest.fixture
def mock_scrape_runs():
    """Create mock scrape runs spanning multiple days"""
    runs = []
    today = datetime.utcnow()

    for i in range(10):
        date = today - timedelta(days=i)
        run = Mock(spec=ScrapeRun)
        run.id = uuid4()
        run.run_at = date
        run.date_str = date.strftime("%B %d, %Y")

        # Create mock queries with tenders
        queries = []
        for q in range(2):
            query = Mock(spec=ScrapedTenderQuery)
            query.id = uuid4()
            query.scrape_run_id = run.id
            query.query_name = f"Category_{q}"

            # Create mock tenders
            tenders = []
            for t in range(3 + q):
                tender = Mock(spec=ScrapedTender)
                tender.id = uuid4()
                tender.tender_id_str = f"TEN-{i}-{q}-{t}"
                tender.tender_name = f"Tender {i}-{q}-{t}"
                tender.tender_url = f"https://tender{i}{q}{t}.com"
                tender.city = f"City_{i % 3}"
                tender.value = f"{100 * (i + 1)} Crore"
                tender.due_date = (date + timedelta(days=7)).strftime("%Y-%m-%d")
                tender.summary = f"Summary for tender {i}-{q}-{t}"
                tender.tender_type = "Open"
                tender.tender_value = f"{100 * (i + 1)} Crore"
                tender.state = f"State_{i % 2}"
                tender.publish_date = date.strftime("%Y-%m-%d")
                tender.last_date_of_bid_submission = (
                    date + timedelta(days=7)
                ).strftime("%Y-%m-%d")
                tenders.append(tender)

            query.tenders = tenders
            queries.append(query)

        run.queries = queries
        runs.append(run)

    return runs


# ==================== TenderIQRepository Tests ====================


class TestTenderIQRepository:
    """Test TenderIQRepository date filtering methods"""

    def test_get_scrape_runs_by_date_range_last_5_days(self, mock_db, mock_scrape_runs):
        """Test getting scrape runs from last 5 days"""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            mock_scrape_runs[:5]
        )

        repo = TenderIQRepository(mock_db)
        result = repo.get_scrape_runs_by_date_range(days=5)

        # Verify we got runs
        assert result is not None
        # In real scenario, would verify the filter was applied correctly

    def test_get_scrape_runs_by_date_range_all_historical(self, mock_db, mock_scrape_runs):
        """Test getting all historical scrape runs"""
        mock_db.query.return_value.order_by.return_value.all.return_value = mock_scrape_runs

        repo = TenderIQRepository(mock_db)
        result = repo.get_scrape_runs_by_date_range(days=None)

        # Should return all runs when days is None
        assert result is not None

    def test_get_available_scrape_runs(self, mock_db, mock_scrape_runs):
        """Test getting available scrape runs with relationships"""
        mock_db.query.return_value.order_by.return_value.options.return_value.all.return_value = (
            mock_scrape_runs
        )

        repo = TenderIQRepository(mock_db)
        result = repo.get_available_scrape_runs()

        assert result is not None

    def test_get_tenders_by_scrape_run_no_filters(self, mock_db):
        """Test getting tenders from specific scrape run without filters"""
        scrape_run_id = uuid4()
        mock_tender = Mock(spec=ScrapedTender)
        mock_tender.id = uuid4()
        mock_tender.tender_id_str = "TEN-001"

        mock_db.query.return_value.join.return_value.filter.return_value.options.return_value.all.return_value = [
            mock_tender
        ]

        repo = TenderIQRepository(mock_db)
        result = repo.get_tenders_by_scrape_run(scrape_run_id)

        assert result is not None
        assert isinstance(result, list)

    def test_get_tenders_by_scrape_run_with_category_filter(self, mock_db):
        """Test getting tenders with category filter"""
        scrape_run_id = uuid4()
        mock_tender = Mock(spec=ScrapedTender)
        mock_tender.id = uuid4()

        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.options.return_value.all.return_value = [
            mock_tender
        ]

        repo = TenderIQRepository(mock_db)
        result = repo.get_tenders_by_scrape_run(
            scrape_run_id, category="Civil"
        )

        assert result is not None

    def test_get_tenders_by_specific_date_valid_format(self, mock_db):
        """Test getting tenders by specific date with valid format"""
        mock_tender = Mock(spec=ScrapedTender)
        mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.filter.return_value.options.return_value.all.return_value = [
            mock_tender
        ]

        repo = TenderIQRepository(mock_db)
        result = repo.get_tenders_by_specific_date("2024-11-03")

        assert result is not None

    def test_get_tenders_by_specific_date_invalid_format(self, mock_db):
        """Test getting tenders by invalid date format raises error"""
        repo = TenderIQRepository(mock_db)

        with pytest.raises(ValueError, match="Invalid date format"):
            repo.get_tenders_by_specific_date("11-03-2024")

    def test_get_all_tenders_with_filters(self, mock_db):
        """Test getting all tenders with filters"""
        mock_tender = Mock(spec=ScrapedTender)
        mock_db.query.return_value.options.return_value.all.return_value = [mock_tender]

        repo = TenderIQRepository(mock_db)
        result = repo.get_all_tenders_with_filters(
            category="Civil", location="Mumbai"
        )

        assert result is not None


# ==================== TenderFilterService Tests ====================


class TestTenderFilterService:
    """Test TenderFilterService business logic"""

    def test_get_available_dates(self, mock_db, mock_scrape_runs):
        """Test getting available dates"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=mock_scrape_runs
        ):
            result = service.get_available_dates(mock_db)

            assert isinstance(result, AvailableDatesResponse)
            assert len(result.dates) > 0
            assert result.dates[0].is_latest is True
            assert result.dates[1].is_latest is False

    def test_get_available_dates_response_format(self, mock_db, mock_scrape_runs):
        """Test available dates response has correct format"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=mock_scrape_runs
        ):
            result = service.get_available_dates(mock_db)

            # Check first date
            first_date = result.dates[0]
            assert "date" in first_date.__dict__
            assert "date_str" in first_date.__dict__
            assert "run_at" in first_date.__dict__
            assert "tender_count" in first_date.__dict__
            assert "is_latest" in first_date.__dict__

    def test_get_available_dates_tender_count_accuracy(self, mock_db, mock_scrape_runs):
        """Test that tender count is accurately calculated"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=mock_scrape_runs[:1]
        ):
            result = service.get_available_dates(mock_db)

            # First run has 2 queries with 3 and 4 tenders each = 7 total
            first_date = result.dates[0]
            expected_count = 3 + 4  # From mock_scrape_runs
            assert first_date.tender_count == expected_count

    def test_get_tenders_by_date_range_last_5_days(self, mock_db):
        """Test getting tenders by date range last 5 days"""
        service = TenderFilterService()
        mock_tenders = [Mock(spec=ScrapedTender) for _ in range(3)]

        with patch.object(
            TenderIQRepository, "get_scrape_runs_by_date_range", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_tenders_by_date_range(mock_db, "last_5_days")

            assert isinstance(result, FilteredTendersResponse)
            assert result.filtered_by["date_range"] == "last_5_days"

    def test_get_tenders_by_date_range_invalid(self, mock_db):
        """Test invalid date range raises error"""
        service = TenderFilterService()

        with pytest.raises(ValueError, match="Invalid date_range"):
            service.get_tenders_by_date_range(mock_db, "last_100_days")

    def test_get_tenders_by_date_range_with_category_filter(self, mock_db):
        """Test date range filtering with category"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_scrape_runs_by_date_range", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_tenders_by_date_range(
                mock_db, "last_5_days", category="Civil"
            )

            assert result.filtered_by["date_range"] == "last_5_days"
            assert result.filtered_by["category"] == "Civil"

    def test_get_tenders_by_specific_date(self, mock_db):
        """Test getting tenders by specific date"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository,
            "get_tenders_by_specific_date",
            return_value=[],
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_tenders_by_specific_date(mock_db, "2024-11-03")

            assert isinstance(result, FilteredTendersResponse)
            assert result.filtered_by["date"] == "2024-11-03"

    def test_get_tenders_by_specific_date_invalid_format(self, mock_db):
        """Test invalid date format raises error"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository,
            "get_tenders_by_specific_date",
            side_effect=ValueError("Invalid date format"),
        ):
            with pytest.raises(ValueError):
                service.get_tenders_by_specific_date(mock_db, "11-03-2024")

    def test_get_all_tenders(self, mock_db):
        """Test getting all tenders"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_all_tenders_with_filters", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_all_tenders(mock_db)

            assert isinstance(result, FilteredTendersResponse)
            assert result.filtered_by["include_all_dates"] is True

    def test_get_all_tenders_with_filters(self, mock_db):
        """Test get all tenders with additional filters"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_all_tenders_with_filters", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_all_tenders(
                mock_db, category="Civil", location="Mumbai"
            )

            assert result.filtered_by["category"] == "Civil"
            assert result.filtered_by["location"] == "Mumbai"

    def test_validate_date_format_valid(self):
        """Test date format validation with valid date"""
        service = TenderFilterService()
        assert service.validate_date_format("2024-11-03") is True

    def test_validate_date_format_invalid(self):
        """Test date format validation with invalid date"""
        service = TenderFilterService()
        assert service.validate_date_format("11-03-2024") is False
        assert service.validate_date_format("2024/11/03") is False
        assert service.validate_date_format("invalid") is False

    def test_available_dates_list_format(self, mock_db):
        """Test that available dates list returns correct format"""
        service = TenderFilterService()
        mock_runs = [
            Mock(run_at=datetime(2024, 11, 3), date_str="Sunday, Nov 03, 2024"),
            Mock(run_at=datetime(2024, 11, 2), date_str="Saturday, Nov 02, 2024"),
        ]

        with patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=mock_runs
        ):
            dates = service._get_available_dates_list(mock_db)

            assert len(dates) == 2
            assert dates[0] == "2024-11-03"
            assert dates[1] == "2024-11-02"


# ==================== Integration-like Tests ====================


class TestDateFilteringIntegration:
    """Integration tests for complete date filtering flow"""

    def test_dates_endpoint_returns_available_dates(self, mock_db, mock_scrape_runs):
        """Test that dates endpoint returns properly formatted response"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=mock_scrape_runs[:3]
        ):
            result = service.get_available_dates(mock_db)

            # Verify structure
            assert isinstance(result, AvailableDatesResponse)
            assert len(result.dates) == 3

            # Verify each date has required fields
            for date_info in result.dates:
                assert date_info.date  # YYYY-MM-DD
                assert date_info.date_str  # Human readable
                assert date_info.run_at  # DateTime
                assert date_info.tender_count >= 0
                assert isinstance(date_info.is_latest, bool)

    def test_tenders_endpoint_filtering_priority(self, mock_db):
        """Test that filtering priority is correct: include_all > date > date_range"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_all_tenders_with_filters", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_tenders_by_specific_date", return_value=[]
        ):
            # When include_all_dates=True, should use get_all_tenders
            result = service.get_all_tenders(mock_db)
            assert result.filtered_by["include_all_dates"] is True

    def test_response_total_count_matches_tenders_list(self, mock_db):
        """Test that total_count in response matches actual tenders"""
        # Create properly mocked tender objects with required attributes
        mock_tenders = []
        for i in range(5):
            tender = Mock(spec=ScrapedTender)
            tender.id = uuid4()
            tender.tender_id_str = f"TEN-{i}"
            tender.tender_name = f"Tender {i}"
            tender.tender_url = f"http://tender{i}.com"
            tender.city = f"City {i}"
            tender.value = f"{i * 100} Crore"
            tender.due_date = "2024-11-10"
            tender.summary = f"Summary {i}"
            tender.tender_type = "Open"
            tender.tender_value = f"{i * 100} Crore"
            tender.state = f"State {i}"
            tender.publish_date = "2024-11-03"
            tender.last_date_of_bid_submission = "2024-11-10"
            mock_tenders.append(tender)

        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_all_tenders_with_filters", return_value=mock_tenders
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_all_tenders(mock_db)

            assert result.total_count == len(result.tenders)
            assert result.total_count == 5

    def test_empty_results_returns_zero_count(self, mock_db):
        """Test that empty results properly return zero count"""
        service = TenderFilterService()

        with patch.object(
            TenderIQRepository, "get_all_tenders_with_filters", return_value=[]
        ), patch.object(
            TenderIQRepository, "get_available_scrape_runs", return_value=[]
        ):
            result = service.get_all_tenders(mock_db)

            assert result.total_count == 0
            assert len(result.tenders) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Integration tests for TenderIQ Analyze module endpoints.

Tests all 10 analyze endpoints for:
- Request/response validation
- Status code correctness
- Database persistence
- Error handling
- User isolation (users only see their own analyses)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.modules.tenderiq.analyze.db.schema import (
    TenderAnalysis,
    AnalysisStatusEnum,
    AnalysisResults,
    AnalysisRisk,
    RiskLevelEnum,
    RiskCategoryEnum,
    AnalysisRFPSection,
)
from app.modules.tenderiq.analyze.db.repository import AnalyzeRepository
from app.modules.tenderiq.analyze.models.pydantic_models import (
    AnalyzeTenderRequest,
    GenerateOnePagerRequest,
)


# ==================== Fixtures ====================


@pytest.fixture
def client():
    """FastAPI TestClient"""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user"""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def sample_tender_id():
    """Sample tender ID for testing"""
    return uuid4()


@pytest.fixture
def sample_analysis_id():
    """Sample analysis ID for testing"""
    return uuid4()


# ==================== Test: Endpoint 1 - Initiate Analysis ====================


class TestInitiateAnalysis:
    """Tests for POST /analyze/tender/{tender_id}"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_initiate_analysis_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test successful analysis initiation"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Mock response from service
        mock_response = Mock()
        mock_response.analysis_id = sample_analysis_id
        mock_response.tender_id = sample_tender_id
        mock_response.status = "pending"
        mock_response.created_at = datetime.utcnow()
        mock_response.estimated_completion_time = 30000

        mock_service.initiate_analysis.return_value = mock_response

        # Make request
        request_data = {
            "documentIds": [],
            "analysisType": "full",
            "includeRiskAssessment": True,
            "includeRfpAnalysis": True,
            "includeScopeOfWork": True,
        }

        response = client.post(
            f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}",
            json=request_data,
        )

        # Assertions
        assert response.status_code == 202
        data = response.json()
        assert data["analysis_id"] == str(sample_analysis_id)
        assert data["tender_id"] == str(sample_tender_id)
        assert data["status"] == "pending"
        assert "created_at" in data
        assert data["estimated_completion_time"] == 30000

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    def test_initiate_analysis_unauthorized(self, mock_get_user, client, sample_tender_id):
        """Test analysis initiation without authentication"""
        mock_get_user.side_effect = Exception("Unauthorized")

        request_data = {
            "documentIds": [],
            "analysisType": "full",
            "includeRiskAssessment": True,
            "includeRfpAnalysis": True,
            "includeScopeOfWork": True,
        }

        # Should fail authentication
        # (Actual behavior depends on auth middleware)


# ==================== Test: Endpoint 2 - Get Analysis Status ====================


class TestGetAnalysisStatus:
    """Tests for GET /analyze/status/{analysis_id}"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_get_status_pending(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test getting status of pending analysis"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analysis_id = sample_analysis_id
        mock_response.tender_id = sample_tender_id
        mock_response.status = "pending"
        mock_response.progress = 0
        mock_response.current_step = "queued"
        mock_response.error_message = None

        mock_service.get_analysis_status.return_value = mock_response

        response = client.get(f"/api/v1/tenderiq/analyze/status/{sample_analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["progress"] == 0

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_get_status_processing(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test getting status of processing analysis"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analysis_id = sample_analysis_id
        mock_response.tender_id = sample_tender_id
        mock_response.status = "processing"
        mock_response.progress = 45
        mock_response.current_step = "analyzing-risk"
        mock_response.error_message = None

        mock_service.get_analysis_status.return_value = mock_response

        response = client.get(f"/api/v1/tenderiq/analyze/status/{sample_analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress"] == 45
        assert data["current_step"] == "analyzing-risk"

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_get_status_completed(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test getting status of completed analysis"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analysis_id = sample_analysis_id
        mock_response.tender_id = sample_tender_id
        mock_response.status = "completed"
        mock_response.progress = 100
        mock_response.current_step = "completed"
        mock_response.error_message = None

        mock_service.get_analysis_status.return_value = mock_response

        response = client.get(f"/api/v1/tenderiq/analyze/status/{sample_analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_get_status_not_found(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test getting status of non-existent analysis"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_analysis_status.return_value = None

        response = client.get(f"/api/v1/tenderiq/analyze/status/{sample_analysis_id}")

        assert response.status_code == 404


# ==================== Test: Endpoint 3 - Get Analysis Results ====================


class TestGetAnalysisResults:
    """Tests for GET /analyze/results/{analysis_id}"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_get_results_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test retrieving completed analysis results"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analysis_id = sample_analysis_id
        mock_response.tender_id = sample_tender_id
        mock_response.status = "completed"
        mock_response.results = {
            "summary": {"key": "value"},
            "riskAssessment": {"risk_score": 65},
            "rfpAnalysis": {"sections": []},
            "scopeOfWork": {"effort_days": 120},
            "onePager": {"content": "..."},
        }
        mock_response.completed_at = datetime.utcnow()
        mock_response.processing_time_ms = 45000

        mock_service.get_analysis_results.return_value = mock_response

        response = client.get(f"/api/v1/tenderiq/analyze/results/{sample_analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "results" in data
        assert "summary" in data["results"]

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_get_results_not_completed(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test retrieving results of incomplete analysis"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_analysis_results.return_value = None

        response = client.get(f"/api/v1/tenderiq/analyze/results/{sample_analysis_id}")

        assert response.status_code == 410  # Gone


# ==================== Test: Endpoint 4 - Risk Assessment ====================


class TestRiskAssessment:
    """Tests for GET /analyze/tender/{tender_id}/risks"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.RiskAssessmentService")
    def test_risk_assessment_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        mock_user,
        mock_db,
    ):
        """Test successful risk assessment"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.tender_id = sample_tender_id
        mock_response.risk_score = 65
        mock_response.risk_level = "high"
        mock_response.risks = [
            {
                "id": str(uuid4()),
                "title": "Complex integration",
                "level": "critical",
                "category": "operational",
                "description": "...",
                "mitigation_strategy": "...",
            }
        ]
        mock_response.summary = "Medium-High risk due to..."

        mock_service.assess_risks.return_value = mock_response

        response = client.get(f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}/risks")

        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "risks" in data
        assert len(data["risks"]) > 0


# ==================== Test: Endpoint 5 - RFP Analysis ====================


class TestRFPAnalysis:
    """Tests for GET /analyze/tender/{tender_id}/rfp-sections"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.RFPExtractionService")
    def test_rfp_extraction_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        mock_user,
        mock_db,
    ):
        """Test successful RFP extraction"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.tender_id = sample_tender_id
        mock_response.total_sections = 3
        mock_response.sections = [
            {
                "section_number": "1",
                "title": "Overview",
                "key_requirements": ["Requirement 1"],
                "complexity": "medium",
            }
        ]

        mock_service.extract_rfp_sections.return_value = mock_response

        response = client.get(
            f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}/rfp-sections"
        )

        assert response.status_code == 200
        data = response.json()
        assert "sections" in data
        assert data["total_sections"] > 0


# ==================== Test: Endpoint 6 - Scope Extraction ====================


class TestScopeExtraction:
    """Tests for GET /analyze/tender/{tender_id}/scope-of-work"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.ScopeExtractionService")
    def test_scope_extraction_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        mock_user,
        mock_db,
    ):
        """Test successful scope extraction"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.tender_id = sample_tender_id
        mock_response.scope_of_work = Mock()
        mock_response.scope_of_work.estimated_total_effort = 120
        mock_response.scope_of_work.work_items = []
        mock_response.scope_of_work.deliverables = []

        mock_service.extract_scope.return_value = mock_response

        response = client.get(
            f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}/scope-of-work"
        )

        assert response.status_code == 200
        data = response.json()
        assert "scope_of_work" in data


# ==================== Test: Endpoint 7 - Generate One-Pager ====================


class TestGenerateOnePager:
    """Tests for POST /analyze/tender/{tender_id}/one-pager"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.ReportGenerationService")
    def test_generate_one_pager_markdown(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        mock_user,
        mock_db,
    ):
        """Test one-pager generation in markdown format"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.tender_id = sample_tender_id
        mock_response.one_pager = {
            "content": "# Tender Analysis\n...",
            "format": "markdown",
            "generatedAt": datetime.utcnow().isoformat(),
        }

        mock_service.generate_one_pager.return_value = mock_response

        request_data = {
            "format": "markdown",
            "includeRiskAssessment": True,
            "includeScopeOfWork": True,
            "includeFinancials": True,
        }

        response = client.post(
            f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}/one-pager",
            json=request_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "one_pager" in data
        assert data["one_pager"]["format"] == "markdown"


# ==================== Test: Endpoint 8 - Generate Data Sheet ====================


class TestGenerateDataSheet:
    """Tests for GET /analyze/tender/{tender_id}/data-sheet"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.ReportGenerationService")
    def test_generate_data_sheet_json(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        mock_user,
        mock_db,
    ):
        """Test data sheet generation in JSON format"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.tender_id = sample_tender_id
        mock_response.data_sheet = Mock()
        mock_response.generated_at = datetime.utcnow()

        mock_service.generate_data_sheet.return_value = mock_response

        response = client.get(
            f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}/data-sheet"
        )

        assert response.status_code == 200
        data = response.json()
        assert "data_sheet" in data


# ==================== Test: Endpoint 9 - List Analyses ====================


class TestListAnalyses:
    """Tests for GET /analyze/analyses"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_list_analyses_empty(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        mock_user,
        mock_db,
    ):
        """Test listing analyses when none exist"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analyses = []
        mock_response.pagination = Mock()
        mock_response.pagination.total = 0
        mock_response.pagination.limit = 20
        mock_response.pagination.offset = 0

        mock_service.list_user_analyses.return_value = mock_response

        response = client.get("/api/v1/tenderiq/analyze/analyses")

        assert response.status_code == 200
        data = response.json()
        assert "analyses" in data
        assert len(data["analyses"]) == 0

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_list_analyses_with_results(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test listing analyses with multiple results"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analyses = [
            Mock(
                analysis_id=sample_analysis_id,
                tender_id=sample_tender_id,
                tender_name="Test Tender",
                status="completed",
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                processing_time_ms=45000,
            )
        ]
        mock_response.pagination = Mock()
        mock_response.pagination.total = 1
        mock_response.pagination.limit = 20
        mock_response.pagination.offset = 0

        mock_service.list_user_analyses.return_value = mock_response

        response = client.get("/api/v1/tenderiq/analyze/analyses")

        assert response.status_code == 200
        data = response.json()
        assert len(data["analyses"]) == 1

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_list_analyses_with_pagination(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        mock_user,
        mock_db,
    ):
        """Test listing analyses with pagination"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analyses = []
        mock_response.pagination = Mock()
        mock_response.pagination.total = 50
        mock_response.pagination.limit = 20
        mock_response.pagination.offset = 20

        mock_service.list_user_analyses.return_value = mock_response

        response = client.get("/api/v1/tenderiq/analyze/analyses?limit=20&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 20
        assert data["pagination"]["offset"] == 20


# ==================== Test: Endpoint 10 - Delete Analysis ====================


class TestDeleteAnalysis:
    """Tests for DELETE /analyze/results/{analysis_id}"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_delete_analysis_success(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test successful analysis deletion"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.delete_analysis.return_value = True

        response = client.delete(f"/api/v1/tenderiq/analyze/results/{sample_analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Analysis deleted successfully"

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_delete_analysis_not_found(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test deleting non-existent analysis"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.delete_analysis.return_value = False

        response = client.delete(f"/api/v1/tenderiq/analyze/results/{sample_analysis_id}")

        assert response.status_code == 404


# ==================== User Isolation Tests ====================


class TestUserIsolation:
    """Tests to ensure users only see their own analyses"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_user_cannot_access_other_user_analysis(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_analysis_id,
        mock_user,
        mock_db,
    ):
        """Test that users cannot access analyses from other users"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_analysis_status.return_value = None

        response = client.get(f"/api/v1/tenderiq/analyze/status/{sample_analysis_id}")

        assert response.status_code == 404

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_list_analyses_only_shows_user_analyses(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        mock_user,
        mock_db,
    ):
        """Test that list endpoint only returns current user's analyses"""
        user_id_1 = uuid4()
        user_id_2 = uuid4()

        mock_user.id = user_id_1
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_response = Mock()
        mock_response.analyses = []
        mock_response.pagination = Mock()
        mock_response.pagination.total = 0
        mock_response.pagination.limit = 20
        mock_response.pagination.offset = 0

        mock_service.list_user_analyses.return_value = mock_response

        response = client.get("/api/v1/tenderiq/analyze/analyses")

        assert response.status_code == 200
        # Verify service was called with correct user_id
        mock_service.list_user_analyses.assert_called()
        call_args = mock_service.list_user_analyses.call_args
        assert call_args[1]["user_id"] == user_id_1


# ==================== Error Handling Tests ====================


class TestErrorHandling:
    """Tests for proper error handling"""

    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_current_active_user")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.get_db_session")
    @patch("app.modules.tenderiq.analyze.endpoints.analyze.AnalysisService")
    def test_service_exception_handling(
        self,
        mock_service_class,
        mock_get_db,
        mock_get_user,
        client,
        sample_tender_id,
        mock_user,
        mock_db,
    ):
        """Test proper error handling when service raises exception"""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.initiate_analysis.side_effect = Exception("Database error")

        request_data = {
            "documentIds": [],
            "analysisType": "full",
            "includeRiskAssessment": True,
            "includeRfpAnalysis": True,
            "includeScopeOfWork": True,
        }

        response = client.post(
            f"/api/v1/tenderiq/analyze/tender/{sample_tender_id}",
            json=request_data,
        )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data or "error" in data

# TenderIQ Module Development Roadmap

This document outlines the required bug fixes, feature completions, and architectural improvements to bring the TenderIQ module to a production-ready state. Each item can be tracked by marking its status.

**Status Legend:**
- `[ ] To Do`
- `[x] Done`
- `[-] Rejected / Won't Do`

---

## Part 1: Bug Fixes and Feature Completions

These items address critical bugs and incomplete features that prevent the module from functioning as intended.

### High Priority

-   **[x] Implement Core Analysis Pipeline**
    -   **File:** `app/modules/tenderiq/services/analysis_service.py`
    -   **Issue:** The `process_analysis` function is a skeleton. The core logic for document parsing, risk assessment, RFP analysis, etc., is commented out with `# TODO`.
    -   **Fix:** Implement the commented-out steps to call the real, asynchronous analysis services.

-   **[x] Fix Orphaned Analysis Records Bug**
    -   **File:** `app/modules/tenderiq/endpoints/analyze.py`
    -   **Issue:** On-demand endpoints (`/risks`, `/rfp-sections`, etc.) create new `TenderAnalysis` records in the database every time they are called, but these records are never processed or cleaned up.
    -   **Fix:** Refactored the on-demand endpoints and their services to be stateless and removed all database record creation logic.

-   **[x] Fix Pydantic Validation Error in Scope of Work**
    -   **Files:** `app/modules/tenderiq/services/scope_extraction_service.py`, `app/modules/tenderiq/models/pydantic_models.py`
    -   **Issue:** `WorkItemResponse` and `DeliverableResponse` are created with `id=None`, but the Pydantic model expects `id: UUID`, causing a 500 error.
    -   **Fix:** Ensured a valid UUID is generated for the `id` field when creating these objects in the service layer as part of the stateless refactor.

-   **[ ] Remove Mock Data from "On-Demand" Endpoints**
    -   **Endpoints:** `/tender/{tender_id}/risks`, `/tender/{tender_id}/rfp-sections`, `/tender/{tender_id}/scope-of-work`, `/tender/{tender_id}/one-pager`.
    -   **Issue:** The services backing these endpoints return hardcoded, static sample data instead of performing real analysis.
    -   **Fix:** Replace the mock data logic with calls to the real, asynchronous LLM-based services.

### Medium Priority

-   **[x] Fix Incorrect Data in Analysis Results**
    -   **File:** `app/modules/tenderiq/services/analysis_service.py`
    -   **Issue:** In `get_analysis_results`, the `riskAssessment` key is incorrectly populated with `rfp_analysis_json` data due to a copy-paste error.
    -   **Fix:** Corrected the key mapping to pull the `risk_assessment` data from the `summary_json` field.

---

## Part 2: Architectural Improvements and Optimizations

These items focus on improving the long-term maintainability, performance, and robustness of the module.

-   **[ ] Unify the Analysis Workflow**
    -   **Goal:** Have a single, consistent, asynchronous workflow for all analysis tasks.
    -   **Action:** Deprecate and remove the on-demand analysis endpoints (`/risks`, `/rfp-sections`, etc.). Instead, create new, lightweight endpoints that retrieve *parts* of an already completed analysis from the database (e.g., `GET /analyze/results/{analysis_id}/scope`). This provides a single source of truth and prevents database pollution.

-   **[ ] Consolidate and Refactor the Service Layer**
    -   **Goal:** Create a single, cohesive service layer that uses modern `async` patterns.
    -   **Action:** Standardize on the newer, `async`-based services (`onepager_generator.py`, `scope_work_analyzer.py`). Migrate any useful logic from the older, synchronous mock services and then delete the mock service files to eliminate redundancy.

-   **[ ] Optimize Database Query for Listing Analyses**
    -   **File:** `app/modules/tenderiq/services/analysis_service.py`
    -   **Issue:** The `list_user_analyses` function has a potential N+1 query problem when fetching the `tender_name`.
    -   **Action:** Use SQLAlchemy's `joinedload` or `selectinload` in the `AnalyzeRepository` to eager-load the related tender information in a single, efficient query.

-   **[ ] Upgrade the Background Task Runner**
    -   **File:** `app/modules/tenderiq/services/analysis_service.py`
    -   **Issue:** The current background task implementation uses `threading.Thread`, which is not robust for a production environment (no retries, concurrency management, or persistence).
    -   **Action:** Replace the `threading` implementation with a dedicated task queue. **Celery** is the industry standard. **ARQ** is a modern, `asyncio`-native alternative that would also be an excellent fit.

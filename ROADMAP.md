# TenderIQ Real-Time Analysis Roadmap

This document outlines the development plan for implementing the real-time, SSE-based tender analysis feature.

**Status Legend:**
- `[ ] To Do`
- `[x] Done`
- `[-] Rejected / Won't Do`

---

## Part 1: Infrastructure Setup (Global)

These tasks involve setting up the core infrastructure that the real-time analysis will depend on.

-   **[x] Integrate Redis**
    -   **Goal:** Add Redis configuration and a shared client for the application.
    -   **Tasks:**
        -   `[x]` Add Redis connection settings (`REDIS_HOST`, `REDIS_PORT`) to `app/config.py`.
        -   `[x]` Create a Redis client utility (e.g., `app/db/redis_client.py`) to provide a reusable connection pool.
        -   `[x]` Add the `redis` and `hiredis` packages to your project dependencies.

-   **[x] Integrate Celery**
    -   **Goal:** Set up an application-wide task queue for background processing.
    -   **Tasks:**
        -   `[x]` Add Celery broker and result backend URLs (using Redis) to `app/config.py`.
        -   `[x]` Create a global Celery app instance (e.g., `app/celery_app.py`) that discovers tasks from all modules.
        -   `[x]` Add `celery` and `redis` (as a broker) to your project dependencies.

---

## Part 2: TenderIQ Analysis Backend

This part focuses on building the background task that performs the analysis and publishes updates.

-   **[x] Create the Main Analysis Task**
    -   **Goal:** Create a Celery task that orchestrates the entire analysis process.
    -   **Tasks:**
        -   `[x]` Create `app/modules/tenderiq/analyze/db/repository.py` to handle database operations for `TenderAnalysis`.
        -   `[x]` Create `app/modules/tenderiq/analyze/events.py` for publishing updates to Redis Pub/Sub.
        -   `[x]` Create `app/modules/tenderiq/analyze/tasks.py`.
        -   `[x]` Define a Celery task `run_tender_analysis(analysis_id)` that will serve as the main entry point.
        -   `[x]` The task will use the repository to update the database at each step and the event publisher to broadcast those updates.

-   **[x] Build Analysis Sub-Services**
    -   **Goal:** Create modular services for each part of the analysis.
    -   **Tasks:**
        -   `[ ]` **Document Parsing Service:** A service that reuses `askai`'s `PDFProcessor` to extract text and save it to the vector store.
        -   `[ ]` **One-Pager Service:** A service that queries the LLM to generate the one-pager data and saves it to the `TenderAnalysis` table.
        -   `[ ]` **Scope of Work Service:** A service that queries the LLM for scope of work data.
        -   `[ ]` **RFP Section Service:** A service that queries the LLM for RFP section data.
        -   `[ ]` **Data Sheet Service:** A service that queries the LLM for data sheet information.

---

## Part 3: TenderIQ Analysis API Endpoint

This part involves creating the user-facing endpoint that streams the analysis results.

-   **[x] Create the SSE Endpoint**
    -   **Goal:** Develop the `GET /tenderiq/analyze/{tender_id}` endpoint.
    -   **Tasks:**
        -   `[x]` Create `app/modules/tenderiq/analyze/endpoints/endpoints.py` and a corresponding router in `app/modules/tenderiq/analyze/router.py`.
        -   `[x]` Implement the endpoint logic:
            1.  On a new request, check the database via the repository for an existing `TenderAnalysis` record.
            2.  **If no record exists:** Create one, set status to `pending`, and trigger the `run_tender_analysis` Celery task.
            3.  **If a record exists with status `completed` or `failed`:** Stream all data from the database record at once and close the connection.
            4.  **If a record exists with status `pending` or `analyzing`:** Stream any existing data from the database record.
            5.  For new or in-progress analyses, subscribe to the Redis Pub/Sub channel and stream live updates to the client.

-   **[x] Define SSE Event Models**
    -   **Goal:** Standardize the format of the messages sent over the stream.
    -   **Tasks:**
        -   `[x]` Create Pydantic models in `app/modules/tenderiq/analyze/models/pydantic_models.py` to define the structure of the SSE events (e.g., `{ "event": "update", "field": "one_pager.project_overview", "data": "..." }`).

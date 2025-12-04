# RoadGPT (backend)

This is the backend for the RoadGPT chatbot. Built with FastAPI.

## Setting up the developer environment

### Linux
1. Clone the repository:
```
git clone https://github.com/WinterSunset95/RoadVisionChatbotBackend && cd RoadVisionChatbotBackend
```
2. (Optional but recommended) Create a virtual environment:
```
python3 -m venv .venv
```
3. Activate the virtual environment:
```
source .venv/bin/activate
```
4. Install dependencies:
```
pip install -r requirements.txt
```
5. Run the startup script:
```
python app.py
```

### Windows
1. Clone the repository:
```
git clone https://github.com/WinterSunset95/RoadVisionChatbotBackend && cd RoadVisionChatbotBackend
```
2. (Optional but recommended) Create a virtual environment:
```
python -m venv .venv
```
3. Activate the virtual environment:
```
.\.venv\Scripts\activate
```
4. Install dependencies:
```
pip install -r requirements.txt
```
5. Run the startup script:
```
python app.py
```

## Requirements (Environment Variables, Credential files, etc.)

1. The following environment variables are required:
    - `GOOGLE_API_KEY`
    - `GOOGLE_APIKEY`
    - `LLAMA_CLOUD_API_KEY`
    - `POSTGRES_USER`
    - `POSTGRES_PASSWORD`
    - `POSTGRES_DB`
    - `WEAVIATE_URL`
    - `WEAVIATE_API_KEY`

2. The following credential files are required:
    - `credentials.json`: Google Drive API credentials
    - `token.json`: Google Drive API token

*Note: The application will absolutely NOT work without the above environment variables and credential files.*
*Please ask the developer for the files*

## Project structure
### Root level `app/`
- `app/main.py`: The main entry point for the FastAPI application.
- `app/config.py`: Application configuration.
- `app/utils.py`: Utility functions for the application.

### `app/api/`
- `v1/`: Aggregates all module level endpoints.

### Shared services and stores `app/core/`

### Database connection handler `app/db/`

### Modules `app/modules/[module_name]/`
This project will be split into multiple modules as the project grows. Each module will have the following
structure:

- `db/`: Module specific database models and repositories.
- `endpoints/`: Module specific API endpoints.
- `services/`: Module specific services and business logic.
- `models/`: Pydantic models for req-res
- `router.py`: Aggregates module endpoints and routes.



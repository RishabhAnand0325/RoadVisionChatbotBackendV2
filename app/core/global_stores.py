
from app.modules.askai.models.document import UploadJob


try:
    upload_jobs: dict[str, UploadJob] = {}
except Exception as e:
    print(f"Failed to initialize upload_jobs: {e}")

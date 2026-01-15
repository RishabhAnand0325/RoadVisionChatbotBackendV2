"""
File storage service for DMS module.
Handles local disk storage operations for MVP (Phase 1).
Future: Can be extended to support S3 and other cloud storage providers.
"""

import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import mimetypes

from app.config import settings

# Define DMS storage root
DMS_ROOT = Path(__file__).parent.parent.parent.parent.parent / "dms"
DMS_ROOT.mkdir(exist_ok=True, parents=True)


class FileStorageService:
    """Handles file storage operations for DMS documents."""

    @staticmethod
    def get_storage_path(document_id: uuid.UUID, filename: str) -> str:
        """
        Generate storage path for a document.
        Format: documents/YYYY/MM/UUID-original_filename

        Args:
            document_id: UUID of the document
            filename: Original filename

        Returns:
            Relative storage path
        """
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        # Generate safe filename
        safe_filename = FileStorageService._sanitize_filename(filename)
        storage_path = f"documents/{year}/{month}/{document_id}-{safe_filename}"
        return storage_path

    @staticmethod
    def get_folder_path(folder_id: uuid.UUID, folder_name: str, parent_path: Optional[str] = None) -> str:
        """
        Generate folder path for DMS hierarchy.

        Args:
            folder_id: UUID of the folder
            folder_name: Name of the folder
            parent_path: Parent folder path if this is a subfolder

        Returns:
            Full folder path like /Legal/Cases/2025/
        """
        safe_name = FileStorageService._sanitize_path_component(folder_name)

        if parent_path:
            # Remove trailing slash from parent if present
            parent_path = parent_path.rstrip("/")
            return f"{parent_path}/{safe_name}/"
        else:
            return f"/{safe_name}/"

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Remove special characters from filename while preserving extension."""
        # Keep only alphanumeric, hyphens, underscores, and dots
        import re
        name, ext = os.path.splitext(filename)
        name = re.sub(r'[^\w\-]', '', name)
        return f"{name}{ext}" if ext else name

    @staticmethod
    def _sanitize_path_component(name: str) -> str:
        """Remove special characters from path component."""
        import re
        return re.sub(r'[^\w\-]', '', name)

    @staticmethod
    def save_file(file_content: bytes, storage_path: str) -> Tuple[bool, str]:
        """
        Save file to disk.

        Args:
            file_content: File content as bytes
            storage_path: Relative storage path

        Returns:
            Tuple of (success, full_path or error_message)
        """
        try:
            full_path = DMS_ROOT / storage_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, 'wb') as f:
                f.write(file_content)

            return True, str(full_path)
        except Exception as e:
            return False, f"Error saving file: {str(e)}"

    @staticmethod
    def read_file(storage_path: str) -> Tuple[bool, Optional[bytes]]:
        """
        Read file from disk.

        Args:
            storage_path: Relative storage path

        Returns:
            Tuple of (success, file_content or None)
        """
        try:
            full_path = DMS_ROOT / storage_path

            if not full_path.exists():
                return False, None

            with open(full_path, 'rb') as f:
                content = f.read()

            return True, content
        except Exception as e:
            return False, None

    @staticmethod
    def delete_file(storage_path: str) -> Tuple[bool, str]:
        """
        Delete file from disk (soft delete by moving to trash).

        Args:
            storage_path: Relative storage path

        Returns:
            Tuple of (success, message)
        """
        try:
            full_path = DMS_ROOT / storage_path

            if not full_path.exists():
                return False, "File not found"

            # Create trash directory
            trash_dir = DMS_ROOT / ".trash"
            trash_dir.mkdir(exist_ok=True, parents=True)

            # Move file to trash with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trash_name = f"{timestamp}_{uuid.uuid4()}_{full_path.name}"
            trash_path = trash_dir / trash_name

            shutil.move(str(full_path), str(trash_path))

            # Clean up empty parent directories
            FileStorageService._cleanup_empty_dirs(full_path.parent)

            return True, f"File moved to trash"
        except Exception as e:
            return False, f"Error deleting file: {str(e)}"

    @staticmethod
    def file_exists(storage_path: str) -> bool:
        """Check if file exists."""
        full_path = DMS_ROOT / storage_path
        return full_path.exists()

    @staticmethod
    def get_file_size(storage_path: str) -> Optional[int]:
        """Get file size in bytes."""
        full_path = DMS_ROOT / storage_path
        try:
            if full_path.exists():
                return full_path.stat().st_size
        except Exception:
            pass
        return None

    @staticmethod
    def create_version(original_path: str, new_storage_path: str) -> Tuple[bool, str]:
        """
        Create a version of a file (for versioning).

        Args:
            original_path: Original file storage path
            new_storage_path: New version storage path

        Returns:
            Tuple of (success, message)
        """
        try:
            original_full = DMS_ROOT / original_path
            new_full = DMS_ROOT / new_storage_path

            if not original_full.exists():
                return False, "Original file not found"

            new_full.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(original_full), str(new_full))

            return True, "Version created successfully"
        except Exception as e:
            return False, f"Error creating version: {str(e)}"

    @staticmethod
    def _cleanup_empty_dirs(path: Path, root: Path = DMS_ROOT, max_depth: int = 3) -> None:
        """
        Recursively clean up empty directories, but not beyond root.

        Args:
            path: Directory to check
            root: Root directory (don't delete above this)
            max_depth: Max recursion depth to prevent excessive cleanup
        """
        if max_depth <= 0 or path == root or not path.is_dir():
            return

        try:
            if not any(path.iterdir()):  # If directory is empty
                path.rmdir()
                # Recursively try to clean parent
                FileStorageService._cleanup_empty_dirs(path.parent, root, max_depth - 1)
        except Exception:
            pass

    @staticmethod
    def get_dms_root() -> Path:
        """Get the DMS root directory path."""
        return DMS_ROOT

    @staticmethod
    def get_full_path(storage_path: str) -> Path:
        """Get the full, absolute path to a stored file."""
        return DMS_ROOT / storage_path

    @staticmethod
    def get_storage_stats() -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage info
        """
        try:
            total_size = 0
            file_count = 0

            for root, dirs, files in os.walk(DMS_ROOT):
                # Skip trash directory
                if '.trash' in root:
                    continue

                for file in files:
                    file_path = Path(root) / file
                    try:
                        total_size += file_path.stat().st_size
                        file_count += 1
                    except Exception:
                        pass

            # Convert bytes to human readable
            def bytes_to_human(bytes_val):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_val < 1024.0:
                        return f"{bytes_val:.2f} {unit}"
                    bytes_val /= 1024.0
                return f"{bytes_val:.2f} TB"

            return {
                'total_size_bytes': total_size,
                'total_size_human': bytes_to_human(total_size),
                'file_count': file_count,
                'dms_root': str(DMS_ROOT)
            }
        except Exception as e:
            return {
                'error': str(e),
                'dms_root': str(DMS_ROOT)
            }

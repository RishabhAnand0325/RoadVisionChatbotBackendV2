"""
Archive utilities for extracting and processing various archive formats.

This module provides unified handling for multiple archive formats:
- ZIP files (.zip)
- RAR files (.rar)
- TAR files (.tar, .tar.gz, .tar.bz2, .tgz)
- 7-Zip files (.7z)

Usage:
    from app.modules.askai.services.archive_utils import (
        detect_archive_type,
        extract_archive,
        is_archive,
        get_archive_members
    )

    # Detect archive type
    archive_type = detect_archive_type("file.zip")  # Returns: 'zip'

    # Extract archive
    extracted_paths = extract_archive("file.zip", "/tmp/extract")

    # Check if file is an archive
    if is_archive(Path("file.rar")):
        # Process as archive
"""

import logging
import zipfile
import tarfile
import gzip
from pathlib import Path
from typing import List, Optional, Dict
import shutil

logger = logging.getLogger(__name__)

# ============================================================================
# SUPPORTED ARCHIVE FORMATS
# ============================================================================

SUPPORTED_ARCHIVE_FORMATS = {
    'zip': '.zip',
    'rar': '.rar',
    'tar': '.tar',
    'gz': '.gz',
    '7z': '.7z',
    'tar_gz': '.tar.gz',
    'tgz': '.tgz',
    'bz2': '.tar.bz2',
}

# Try to import optional libraries for RAR and 7Z support
try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False
    logger.warning("rarfile not installed. RAR archive support disabled. Install with: pip install rarfile")

try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False
    logger.warning("py7zr not installed. 7Z archive support disabled. Install with: pip install py7zr")


# ============================================================================
# ARCHIVE DETECTION
# ============================================================================

def is_archive(file_path: Path) -> bool:
    """
    Check if a file is an archive based on its extension.

    Simple extension-based check. For more robust detection, use
    detect_archive_type() which can validate archive integrity.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file extension matches a known archive format
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    suffix = file_path.suffix.lower()
    name_lower = file_path.name.lower()

    # Check common archive extensions
    return (
        suffix in ['.zip', '.rar', '.7z', '.gz', '.bz2']
        or name_lower.endswith('.tar.gz')
        or name_lower.endswith('.tar.bz2')
        or suffix == '.tar'
        or name_lower.endswith('.tgz')
    )


def detect_archive_type(file_path: str) -> Optional[str]:
    """
    Detect the archive type of a file.

    Uses extension-based detection with validation where possible.
    Returns the archive type or None if file is not a recognized archive.

    Supported types:
    - 'zip': ZIP archives
    - 'rar': RAR archives
    - 'tar': TAR archives
    - 'tar_gz': TAR + GZIP archives
    - 'tar_bz2': TAR + BZIP2 archives
    - '7z': 7-Zip archives

    Args:
        file_path: Path to the file to check

    Returns:
        Archive type string or None if not an archive
    """
    if not isinstance(file_path, str):
        file_path = str(file_path)

    name_lower = file_path.lower()

    # Check for specific compound extensions first
    if name_lower.endswith('.tar.gz') or name_lower.endswith('.tgz'):
        return 'tar_gz'
    if name_lower.endswith('.tar.bz2'):
        return 'tar_bz2'

    # Check single extensions
    if name_lower.endswith('.zip'):
        return 'zip'
    elif name_lower.endswith('.rar'):
        return 'rar'
    elif name_lower.endswith('.tar'):
        return 'tar'
    elif name_lower.endswith('.7z'):
        return '7z'
    elif name_lower.endswith('.gz'):
        # Could be .tar.gz (checked above) or just .gz
        return 'gz'
    elif name_lower.endswith('.bz2'):
        return 'bz2'

    return None


def get_archive_members(archive_path: str) -> Optional[List[Dict]]:
    """
    Get list of files contained in an archive.

    Returns metadata about each file in the archive:
    - path: File path within archive
    - size: Uncompressed size in bytes
    - is_dir: Whether entry is a directory

    Useful for:
    - Validating archive contents before extraction
    - Checking file counts
    - Pre-filtering files

    Args:
        archive_path: Path to the archive file

    Returns:
        List of member info dicts, or None if archive reading failed
    """
    archive_type = detect_archive_type(archive_path)

    if not archive_type:
        logger.warning(f"Unknown archive type: {archive_path}")
        return None

    try:
        members = []

        if archive_type == 'zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for info in zf.infolist():
                    members.append({
                        'path': info.filename,
                        'size': info.file_size,
                        'is_dir': info.is_dir()
                    })

        elif archive_type == 'tar' or archive_type.startswith('tar_'):
            mode = 'r'
            if archive_type == 'tar_gz':
                mode = 'r:gz'
            elif archive_type == 'tar_bz2':
                mode = 'r:bz2'

            with tarfile.open(archive_path, mode) as tf:
                for member in tf.getmembers():
                    members.append({
                        'path': member.name,
                        'size': member.size,
                        'is_dir': member.isdir()
                    })

        elif archive_type == 'rar' and HAS_RARFILE:
            with rarfile.RarFile(archive_path, 'r') as rf:
                for info in rf.infolist():
                    members.append({
                        'path': info.filename,
                        'size': info.file_size,
                        'is_dir': info.is_dir()
                    })

        elif archive_type == '7z' and HAS_PY7ZR:
            with py7zr.SevenZipFile(archive_path, 'r') as zf:
                for name, info in zf.list():
                    members.append({
                        'path': name,
                        'size': info.uncompressed,
                        'is_dir': info.is_directory
                    })

        else:
            logger.error(f"Archive type {archive_type} not supported or dependencies missing")
            return None

        return members

    except Exception as e:
        logger.error(f"Failed to read archive members from {archive_path}: {e}")
        return None


# ============================================================================
# ARCHIVE EXTRACTION
# ============================================================================

def extract_archive(
    archive_path: str,
    extract_to: str,
    max_files: int = 100,
    max_size_mb: int = 500
) -> Optional[List[Path]]:
    """
    Extract an archive to a directory.

    Supports multiple archive formats with automatic format detection.
    Includes safety checks for:
    - Maximum number of files
    - Maximum extracted size
    - Corrupted files (skips with warning)

    The function returns a list of extracted file paths. Directories are
    NOT included in the result (only files).

    Args:
        archive_path: Path to the archive file
        extract_to: Directory to extract into
        max_files: Maximum files allowed in archive (prevents extraction bombs)
        max_size_mb: Maximum total uncompressed size in MB

    Returns:
        List of extracted file paths (Path objects), or None if extraction failed

    Raises:
        ValueError: If safety checks fail (too many files, too large, etc.)
    """
    archive_type = detect_archive_type(archive_path)

    if not archive_type:
        logger.error(f"Unknown or unsupported archive type: {archive_path}")
        return None

    # Pre-check: validate archive contents before extracting
    members = get_archive_members(archive_path)
    if members is None:
        logger.error(f"Failed to read archive: {archive_path}")
        return None

    file_count = len([m for m in members if not m['is_dir']])
    total_size = sum(m['size'] for m in members)

    # Safety checks
    if file_count > max_files:
        raise ValueError(
            f"Archive contains {file_count} files, exceeds limit of {max_files}. "
            f"Potential extraction bomb."
        )

    total_size_mb = total_size / (1024 * 1024)
    if total_size_mb > max_size_mb:
        raise ValueError(
            f"Archive would extract to {total_size_mb:.1f}MB, "
            f"exceeds limit of {max_size_mb}MB"
        )

    logger.info(
        f"Extracting archive: {Path(archive_path).name} "
        f"({file_count} files, {total_size_mb:.1f}MB)"
    )

    # Create extraction directory
    extract_path = Path(extract_to)
    extract_path.mkdir(parents=True, exist_ok=True)

    extracted_files = []

    try:
        if archive_type == 'zip':
            extracted_files = _extract_zip(archive_path, extract_to)

        elif archive_type in ['tar', 'tar_gz', 'tar_bz2']:
            extracted_files = _extract_tar(archive_path, extract_to, archive_type)

        elif archive_type == 'rar':
            if not HAS_RARFILE:
                raise ImportError("rarfile not installed. Install with: pip install rarfile")
            extracted_files = _extract_rar(archive_path, extract_to)

        elif archive_type == '7z':
            if not HAS_PY7ZR:
                raise ImportError("py7zr not installed. Install with: pip install py7zr")
            extracted_files = _extract_7z(archive_path, extract_to)

        else:
            logger.error(f"Archive type {archive_type} not yet implemented")
            return None

        logger.info(f"Successfully extracted {len(extracted_files)} files from archive")
        return extracted_files

    except Exception as e:
        logger.error(f"Failed to extract archive {archive_path}: {e}")
        return None


def _extract_zip(archive_path: str, extract_to: str) -> List[Path]:
    """
    Extract a ZIP archive.

    Args:
        archive_path: Path to ZIP file
        extract_to: Directory to extract into

    Returns:
        List of extracted file paths
    """
    extracted_files = []

    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            # Extract all files
            zf.extractall(extract_to)

            # Return list of file paths (exclude directories)
            for member in zf.namelist():
                member_path = Path(extract_to) / member
                if member_path.is_file():
                    extracted_files.append(member_path)

    except zipfile.BadZipFile as e:
        logger.error(f"Corrupted ZIP archive {archive_path}: {e}")
        raise

    return extracted_files


def _extract_tar(archive_path: str, extract_to: str, archive_type: str) -> List[Path]:
    """
    Extract a TAR archive (supports .tar, .tar.gz, .tar.bz2).

    Args:
        archive_path: Path to TAR file
        extract_to: Directory to extract into
        archive_type: Type of archive ('tar', 'tar_gz', 'tar_bz2')

    Returns:
        List of extracted file paths
    """
    extracted_files = []

    # Determine compression mode
    mode = 'r'
    if archive_type == 'tar_gz':
        mode = 'r:gz'
    elif archive_type == 'tar_bz2':
        mode = 'r:bz2'

    try:
        with tarfile.open(archive_path, mode) as tf:
            # Extract all files
            tf.extractall(path=extract_to)

            # Return list of file paths (exclude directories)
            for member in tf.getmembers():
                member_path = Path(extract_to) / member.name
                if member_path.is_file():
                    extracted_files.append(member_path)

    except tarfile.ReadError as e:
        logger.error(f"Corrupted TAR archive {archive_path}: {e}")
        raise

    return extracted_files


def _extract_rar(archive_path: str, extract_to: str) -> List[Path]:
    """
    Extract a RAR archive.

    Requires rarfile package: pip install rarfile

    Args:
        archive_path: Path to RAR file
        extract_to: Directory to extract into

    Returns:
        List of extracted file paths
    """
    if not HAS_RARFILE:
        raise ImportError("rarfile not installed. Install with: pip install rarfile")

    extracted_files = []

    try:
        with rarfile.RarFile(archive_path, 'r') as rf:
            # Extract all files
            rf.extractall(path=extract_to)

            # Return list of file paths (exclude directories)
            for member in rf.namelist():
                member_path = Path(extract_to) / member
                if member_path.is_file():
                    extracted_files.append(member_path)

    except rarfile.BadRarFile as e:
        logger.error(f"Corrupted RAR archive {archive_path}: {e}")
        raise

    return extracted_files


def _extract_7z(archive_path: str, extract_to: str) -> List[Path]:
    """
    Extract a 7-Zip archive.

    Requires py7zr package: pip install py7zr

    Args:
        archive_path: Path to 7Z file
        extract_to: Directory to extract into

    Returns:
        List of extracted file paths
    """
    if not HAS_PY7ZR:
        raise ImportError("py7zr not installed. Install with: pip install py7zr")

    extracted_files = []

    try:
        with py7zr.SevenZipFile(archive_path, 'r') as zf:
            # Extract all files
            zf.extractall(path=extract_to)

            # Return list of file paths (exclude directories)
            for name, _ in zf.list():
                member_path = Path(extract_to) / name
                if member_path.is_file():
                    extracted_files.append(member_path)

    except py7zr.Bad7zFile as e:
        logger.error(f"Corrupted 7Z archive {archive_path}: {e}")
        raise

    return extracted_files


# ============================================================================
# CLEANUP UTILITIES
# ============================================================================

def cleanup_extracted_files(extracted_files: List[Path]) -> None:
    """
    Clean up extracted archive files.

    Removes files from extracted_files list. Useful when processing
    extracted files and you want to clean them up afterward.

    Args:
        extracted_files: List of file paths to remove
    """
    for file_path in extracted_files:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path}: {e}")

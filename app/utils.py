import hashlib
from datetime import datetime
from pathlib import Path

def get_consistent_timestamp() -> str:
    """Return ISO format timestamp"""
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def ensure_directory_exists(path: Path):
    """Ensure directory exists with proper permissions"""
    path.mkdir(parents=True, exist_ok=True)

def get_file_hash(file_path: str) -> str:
    """Generate unique hash for file"""
    hasher = hashlib.md5()
    # Using 'rb' for binary read ensures consistency across platforms
    with open(file_path, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes is None:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

"""
User cache scanner: ~/.cache breakdown by application.
"""

import os
import subprocess
from typing import NamedTuple


class CacheEntry(NamedTuple):
    name: str
    path: str
    size_bytes: int


def _dir_size_bytes(path: str) -> int:
    try:
        res = subprocess.run(['du', '-sk', path], capture_output=True, text=True, timeout=10)
        return int(res.stdout.split()[0]) * 1024
    except Exception:
        return 0


def get_user_cache_entries() -> list[CacheEntry]:
    """Return top-level entries in ~/.cache sorted by size descending."""
    cache_dir = os.path.join(os.path.expanduser('~'), '.cache')
    if not os.path.isdir(cache_dir):
        return []

    entries = []
    try:
        for entry in os.scandir(cache_dir):
            try:
                if entry.is_dir(follow_symlinks=False):
                    size = _dir_size_bytes(entry.path)
                else:
                    size = entry.stat(follow_symlinks=False).st_size
                if size > 0:
                    entries.append(CacheEntry(name=entry.name, path=entry.path, size_bytes=size))
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except PermissionError:
        pass

    return sorted(entries, key=lambda e: e.size_bytes, reverse=True)

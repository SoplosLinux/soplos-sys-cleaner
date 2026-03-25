"""
Temporary files scanner: /tmp and /var/tmp.
Scans only top-level entries to avoid hanging on large build trees.
"""

import os
import stat as stat_module
import subprocess
import time
from typing import NamedTuple


class TempEntry(NamedTuple):
    path: str
    size_bytes: int
    age_days: float
    is_dir: bool


# Top-level directories to skip — active session or system sockets
_SKIP_DIRS = {
    '.X11-unix', '.ICE-unix', '.XIM-unix', '.font-unix', '.Test-unix',
}
_SKIP_PREFIXES = ('systemd-private-', 'snap-private-')


def _dir_size_bytes(path: str) -> int:
    """Return directory size in bytes using du for speed."""
    try:
        res = subprocess.run(
            ['du', '-sk', path],
            capture_output=True, text=True, timeout=10
        )
        return int(res.stdout.split()[0]) * 1024
    except Exception:
        return 0


def get_temp_entries(min_age_days: float = 1.0) -> list[TempEntry]:
    """
    Returns top-level entries in /tmp and /var/tmp older than min_age_days.
    Directories are returned as single entries with their total size.
    """
    entries = []
    now = time.time()

    for base_path in ('/tmp', '/var/tmp'):
        if not os.path.isdir(base_path):
            continue
        try:
            for entry in os.scandir(base_path):
                # Skip known active session dirs
                if entry.name in _SKIP_DIRS:
                    continue
                if any(entry.name.startswith(p) for p in _SKIP_PREFIXES):
                    continue
                try:
                    st = entry.stat(follow_symlinks=False)
                    # Skip sockets, named pipes and symlinks
                    if stat_module.S_ISSOCK(st.st_mode) or \
                       stat_module.S_ISFIFO(st.st_mode) or \
                       stat_module.S_ISLNK(st.st_mode):
                        continue
                    age_days = (now - st.st_mtime) / 86400
                    if age_days < min_age_days:
                        continue

                    is_dir = entry.is_dir(follow_symlinks=False)
                    size = _dir_size_bytes(entry.path) if is_dir else st.st_size

                    entries.append(TempEntry(
                        path=entry.path,
                        size_bytes=size,
                        age_days=age_days,
                        is_dir=is_dir,
                    ))
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except PermissionError:
            continue

    return sorted(entries, key=lambda e: e.size_bytes, reverse=True)

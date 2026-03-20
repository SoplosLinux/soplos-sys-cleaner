"""
Temporary files scanner: /tmp and /var/tmp.
"""

import os
import stat as stat_module
import time
from typing import NamedTuple


class TempEntry(NamedTuple):
    path: str
    size_bytes: int
    age_days: float
    is_dir: bool


def get_temp_entries(min_age_days: float = 1.0) -> list[TempEntry]:
    """Returns temp files older than min_age_days."""
    entries = []
    now = time.time()
    temp_paths = ['/tmp', '/var/tmp']
    exclude_dirs = {'.X11-unix', '.ICE-unix', '.XIM-unix', '.font-unix', '.Test-unix'}

    for base_path in temp_paths:
        if not os.path.isdir(base_path):
            continue
        try:
            for root, dirs, files in os.walk(base_path, topdown=True):
                # Exclude critical session/system sockets and mounts
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('systemd-private-') and not d.startswith('snap-private-')]
                
                for f in files:
                    full_path = os.path.join(root, f)
                    try:
                        stat = os.lstat(full_path)
                        # Skip sockets, named pipes and symlinks — active session files
                        if stat_module.S_ISSOCK(stat.st_mode) or stat_module.S_ISFIFO(stat.st_mode) or stat_module.S_ISLNK(stat.st_mode):
                            continue
                        age_days = (now - stat.st_mtime) / 86400
                        if age_days < min_age_days:
                            continue

                        entries.append(TempEntry(
                            path=full_path,
                            size_bytes=stat.st_size,
                            age_days=age_days,
                            is_dir=False,
                        ))
                    except (PermissionError, FileNotFoundError):
                        continue
        except PermissionError:
            continue

    return sorted(entries, key=lambda e: e.size_bytes, reverse=True)



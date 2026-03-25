"""
System logs scanner: /var/log and journald.
Requires root to read all entries.
"""

import os
import subprocess
from typing import NamedTuple


class LogEntry(NamedTuple):
    name: str
    path: str
    size_bytes: int


class JournaldInfo(NamedTuple):
    size_bytes: int
    disk_usage_str: str   # raw string from journalctl


def _dir_size_bytes(path: str) -> int:
    try:
        res = subprocess.run(['du', '-sk', path], capture_output=True, text=True, timeout=10)
        return int(res.stdout.split()[0]) * 1024
    except Exception:
        return 0


def get_varlog_entries() -> list[LogEntry]:
    """Return top-level entries in /var/log sorted by size descending."""
    log_dir = '/var/log'
    if not os.path.isdir(log_dir):
        return []

    entries = []
    try:
        for entry in os.scandir(log_dir):
            try:
                if entry.is_dir(follow_symlinks=False):
                    size = _dir_size_bytes(entry.path)
                else:
                    size = entry.stat(follow_symlinks=False).st_size
                if size > 0:
                    entries.append(LogEntry(name=entry.name, path=entry.path, size_bytes=size))
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except PermissionError:
        pass

    return sorted(entries, key=lambda e: e.size_bytes, reverse=True)


def get_journald_info() -> JournaldInfo:
    """Return journald disk usage."""
    try:
        result = subprocess.run(
            ['journalctl', '--disk-usage'],
            capture_output=True, text=True, timeout=10
        )
        # Output: "Archived and active journals take up X.XG (or similar) in the filesystem."
        line = result.stdout.strip()
        # Extract size string
        size_bytes = 0
        for part in line.split():
            size_bytes = _parse_journal_size(part)
            if size_bytes > 0:
                break
        return JournaldInfo(size_bytes=size_bytes, disk_usage_str=line)
    except Exception:
        return JournaldInfo(size_bytes=0, disk_usage_str='')


def _parse_journal_size(s: str) -> int:
    """Parse journalctl size strings like '1.2G', '345M', '12K'."""
    try:
        s = s.strip('.')
        if s.endswith('G'):
            return int(float(s[:-1]) * 1024**3)
        elif s.endswith('M'):
            return int(float(s[:-1]) * 1024**2)
        elif s.endswith('K'):
            return int(float(s[:-1]) * 1024)
        elif s.endswith('B') and len(s) > 1:
            return int(float(s[:-1]))
    except Exception:
        pass
    return 0

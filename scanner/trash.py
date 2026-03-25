"""
Trash scanner: ~/.local/share/Trash
"""

import os
import subprocess
from typing import NamedTuple


class TrashInfo(NamedTuple):
    files_count: int
    size_bytes: int
    path: str


def _dir_size_bytes(path: str) -> int:
    try:
        res = subprocess.run(['du', '-sk', path], capture_output=True, text=True, timeout=10)
        return int(res.stdout.split()[0]) * 1024
    except Exception:
        return 0


def get_trash_info() -> TrashInfo:
    """Return trash size and file count."""
    trash_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', 'Trash')
    files_dir = os.path.join(trash_dir, 'files')

    if not os.path.isdir(trash_dir):
        return TrashInfo(files_count=0, size_bytes=0, path=trash_dir)

    count = 0
    if os.path.isdir(files_dir):
        try:
            count = sum(1 for _ in os.scandir(files_dir))
        except PermissionError:
            pass

    size = _dir_size_bytes(trash_dir)
    return TrashInfo(files_count=count, size_bytes=size, path=trash_dir)

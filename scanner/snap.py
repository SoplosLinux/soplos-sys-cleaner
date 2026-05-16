"""
Snap scanner: installed snaps and old/disabled revisions.
"""

import os
import subprocess
from typing import NamedTuple


class SnapApp(NamedTuple):
    name: str
    version: str
    channel: str
    size_bytes: int


class SnapRevision(NamedTuple):
    name: str
    revision: str
    size_bytes: int


def is_snap_available() -> bool:
    """Returns True if snap is installed on this system."""
    try:
        result = subprocess.run(['snap', 'version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, Exception):
        return False


def get_installed_snaps() -> list[SnapApp]:
    """Returns all currently active/installed snaps (user-installed, excludes base/snapd)."""
    if not is_snap_available():
        return []

    # These are infrastructure snaps that should not be removed by the user
    _SKIP = {'core', 'core18', 'core20', 'core22', 'core24', 'snapd'}

    apps = []
    try:
        result = subprocess.run(
            ['snap', 'list'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []

        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return []

        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            name = parts[0]
            if name in _SKIP:
                continue
            version = parts[1]
            channel = parts[3] if len(parts) > 3 else ''
            size = _get_snap_total_size(name)
            apps.append(SnapApp(name=name, version=version, channel=channel, size_bytes=size))

    except Exception as e:
        print(f"[snap] Error listing installed snaps: {e}")

    return sorted(apps, key=lambda a: a.size_bytes, reverse=True)


def get_snap_old_revisions() -> list[SnapRevision]:
    """Returns disabled snap revisions that can be safely removed."""
    if not is_snap_available():
        return []

    revisions = []
    try:
        result = subprocess.run(
            ['snap', 'list', '--all'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []

        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return []

        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            name = parts[0]
            revision = parts[2]
            if 'disabled' in line.lower():
                size = _get_snap_revision_size(name, revision)
                revisions.append(SnapRevision(name=name, revision=revision, size_bytes=size))

    except Exception as e:
        print(f"[snap] Error listing old revisions: {e}")

    return sorted(revisions, key=lambda r: r.size_bytes, reverse=True)


def get_snap_leftover_dirs(installed_names: list[str]) -> list[str]:
    """
    Returns ~/snap/{name} dirs that exist on disk but whose snap is no longer installed.
    These are leftover user-data dirs from previously removed snaps.
    """
    leftover = []
    snap_user_dir = os.path.expanduser('~/snap')
    if not os.path.isdir(snap_user_dir):
        return leftover
    installed = set(installed_names)
    try:
        for entry in os.scandir(snap_user_dir):
            if entry.is_dir() and entry.name not in installed:
                leftover.append(entry.path)
    except Exception:
        pass
    return sorted(leftover)


def _get_snap_total_size(name: str) -> int:
    snap_path = f'/snap/{name}'
    try:
        res = subprocess.run(['du', '-sk', snap_path], capture_output=True, text=True, timeout=15)
        return int(res.stdout.split()[0]) * 1024
    except Exception:
        return 0


def _get_snap_revision_size(name: str, revision: str) -> int:
    snap_path = f'/snap/{name}/{revision}'
    try:
        res = subprocess.run(['du', '-sk', snap_path], capture_output=True, text=True, timeout=10)
        return int(res.stdout.split()[0]) * 1024
    except Exception:
        return 0

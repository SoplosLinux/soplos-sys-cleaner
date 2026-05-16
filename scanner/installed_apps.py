"""
Installed apps scanner: lists manually installed packages via apt-mark + dpkg-query.
No root required for scanning.
"""

import os
import subprocess
from typing import NamedTuple


class AppInfo(NamedTuple):
    name: str
    summary: str
    section: str
    size_kb: int
    has_desktop: bool


def get_manually_installed() -> set[str]:
    """Returns the set of manually installed package names."""
    try:
        result = subprocess.run(
            ['apt-mark', 'showmanual'],
            capture_output=True, text=True, timeout=15
        )
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except Exception:
        return set()


def get_desktop_packages() -> set[str]:
    """Returns package names that own a .desktop file in /usr/share/applications/."""
    desktop_dir = '/usr/share/applications'
    names = set()
    if not os.path.isdir(desktop_dir):
        return names
    try:
        files = [
            os.path.join(desktop_dir, f)
            for f in os.listdir(desktop_dir)
            if f.endswith('.desktop')
        ]
        if not files:
            return names
        result = subprocess.run(
            ['dpkg', '-S'] + files,
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.splitlines():
            if ':' in line:
                names.add(line.split(':')[0].strip())
    except Exception:
        pass
    return names


def _is_system_package(name: str, section: str) -> bool:
    """Returns True for packages managed by other tabs (firmware, kernel)."""
    s = section.lower().strip()
    if 'kernel' in s or 'firmware' in s:
        return True
    if name.startswith('firmware-') or name in ('linux-firmware', 'linux-firmware-nonfree'):
        return True
    if (name.startswith('linux-image-') or name.startswith('linux-headers-') or
            name.startswith('linux-modules-') or name.startswith('linux-kbuild-') or
            name.startswith('linux-libc-dev') or name.startswith('linux-compiler-')):
        return True
    return False


def get_installed_apps() -> list[AppInfo]:
    """Returns manually installed packages with metadata, sorted by size descending."""
    manual = get_manually_installed()
    if not manual:
        return []

    desktop_pkgs = get_desktop_packages()

    try:
        result = subprocess.run(
            ['dpkg-query', '-W',
             '-f=${Package}\t${Installed-Size}\t${binary:Summary}\t${Section}\n'],
            capture_output=True, text=True, timeout=30
        )
    except Exception:
        return []

    apps = []
    for line in result.stdout.splitlines():
        parts = line.split('\t', 3)
        if len(parts) < 4:
            continue
        name, size_str, summary, section = parts
        name = name.strip()
        if name not in manual:
            continue
        if _is_system_package(name, section.strip()):
            continue
        try:
            size_kb = int(size_str.strip())
        except ValueError:
            size_kb = 0
        apps.append(AppInfo(
            name=name,
            summary=summary.strip(),
            section=section.strip(),
            size_kb=size_kb,
            has_desktop=(name in desktop_pkgs),
        ))

    return sorted(apps, key=lambda a: a.size_kb, reverse=True)

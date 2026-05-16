"""
APT cache scanner: measures cache size and orphaned packages.
"""

import os
import subprocess


def get_apt_cache_info() -> dict:
    """Returns APT cache size (.deb files) and apt lists size."""
    cache_path = '/var/cache/apt/archives'
    total_size = 0
    deb_count = 0

    if os.path.isdir(cache_path):
        for entry in os.scandir(cache_path):
            if entry.is_file() and entry.name.endswith('.deb'):
                try:
                    total_size += entry.stat().st_size
                    deb_count += 1
                except OSError:
                    pass

    lists_path = '/var/lib/apt/lists'
    lists_size = 0
    if os.path.isdir(lists_path):
        for entry in os.scandir(lists_path):
            if entry.is_file():
                try:
                    lists_size += entry.stat().st_size
                except OSError:
                    pass

    return {
        'path': cache_path,
        'size_bytes': total_size,
        'deb_count': deb_count,
        'lists_size_bytes': lists_size,
    }


def get_apt_cache_debs() -> list[dict]:
    """Returns individual .deb files in the APT cache with name and size."""
    cache_path = '/var/cache/apt/archives'
    debs = []
    if os.path.isdir(cache_path):
        for entry in os.scandir(cache_path):
            if entry.is_file() and entry.name.endswith('.deb'):
                try:
                    debs.append({'name': entry.name, 'path': entry.path, 'size_bytes': entry.stat().st_size})
                except OSError:
                    pass
    return sorted(debs, key=lambda d: d['size_bytes'], reverse=True)


def get_autoremove_packages() -> list[str]:
    """Returns list of packages flagged for autoremoval by apt."""
    packages = []
    try:
        result = subprocess.run(
            ['apt-get', '--dry-run', 'autoremove'],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith('Remv '):
                pkg = line.split()[1]
                packages.append(pkg)
    except Exception as e:
        print(f"[cache] Error getting autoremove list: {e}")
    return packages



"""
Flatpak scanner: detects unused runtimes removable via 'flatpak uninstall --unused'.
"""

import subprocess
from typing import NamedTuple


class FlatpakEntry(NamedTuple):
    ref: str       # e.g. runtime/org.freedesktop.Platform/x86_64/22.08
    name: str      # human-readable part
    size_bytes: int


def flatpak_available() -> bool:
    try:
        result = subprocess.run(['flatpak', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, Exception):
        return False


def get_unused_flatpak_entries() -> list[FlatpakEntry]:
    """Return list of unused Flatpak runtimes that can be removed."""
    if not flatpak_available():
        return []

    try:
        # --columns=application,size gives us ref and size
        result = subprocess.run(
            ['flatpak', 'list', '--runtime', '--columns=application,size'],
            capture_output=True, text=True, timeout=15
        )
        all_refs = {}
        for line in result.stdout.splitlines():
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                ref, size_str = parts[0].strip(), parts[1].strip()
                # Convert human size to bytes (approximate)
                size_bytes = _parse_flatpak_size(size_str)
                all_refs[ref] = size_bytes

        # Get unused refs
        unused_result = subprocess.run(
            ['flatpak', 'list', '--runtime', '--unused', '--columns=application,size'],
            capture_output=True, text=True, timeout=15
        )

        entries = []
        for line in unused_result.stdout.splitlines():
            parts = line.strip().split('\t')
            if len(parts) >= 1:
                ref = parts[0].strip()
                if not ref:
                    continue
                size_bytes = _parse_flatpak_size(parts[1].strip()) if len(parts) >= 2 else 0
                name = ref.split('/')[-1] if '/' in ref else ref
                entries.append(FlatpakEntry(ref=ref, name=name, size_bytes=size_bytes))

        return sorted(entries, key=lambda e: e.size_bytes, reverse=True)

    except Exception:
        return []


def _parse_flatpak_size(size_str: str) -> int:
    """Convert flatpak size string (e.g. '234.5 MB') to bytes."""
    try:
        parts = size_str.split()
        value = float(parts[0])
        unit = parts[1].upper() if len(parts) > 1 else 'B'
        multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
        return int(value * multipliers.get(unit, 1))
    except Exception:
        return 0

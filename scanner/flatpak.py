"""
Flatpak scanner: lists installed apps and detects unused runtimes.
Sizes are computed via du on the flatpak data directories.
"""

import os
import subprocess
from typing import NamedTuple

# Flatpak installation roots (user first, then system)
_FLATPAK_ROOTS = [
    os.path.expanduser('~/.local/share/flatpak'),
    '/var/lib/flatpak',
]


class FlatpakApp(NamedTuple):
    app_id: str     # e.g. com.spotify.Client
    name: str       # human-readable name, e.g. Spotify
    version: str    # e.g. 1.2.3
    size_bytes: int


class FlatpakEntry(NamedTuple):
    ref: str       # e.g. org.freedesktop.Platform.GL.default/x86_64/25.08
    name: str      # human-readable part
    size_bytes: int


def flatpak_available() -> bool:
    try:
        result = subprocess.run(['flatpak', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, Exception):
        return False


def get_installed_flatpak_apps() -> list[FlatpakApp]:
    """Return list of installed Flatpak applications with their disk size."""
    if not flatpak_available():
        return []
    try:
        result = subprocess.run(
            ['flatpak', 'list', '--app', '--columns=application,name,version,arch,branch'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []
        apps = []
        for line in result.stdout.splitlines():
            parts = line.strip().split('\t')
            if not parts or not parts[0].strip():
                continue
            app_id = parts[0].strip()
            name = parts[1].strip() if len(parts) >= 2 else app_id
            version = parts[2].strip() if len(parts) >= 3 else ''
            arch = parts[3].strip() if len(parts) >= 4 else 'x86_64'
            branch = parts[4].strip() if len(parts) >= 5 else 'stable'
            size_bytes = _du_flatpak('app', app_id, arch, branch)
            apps.append(FlatpakApp(app_id=app_id, name=name, version=version, size_bytes=size_bytes))
        return sorted(apps, key=lambda a: a.size_bytes, reverse=True)
    except Exception:
        return []


# Extension segments that are loaded dynamically by gaming/media Flatpak apps
# (e.g. Lutris, Bottles). These are never truly "unused" even if flatpak's
# dependency resolver can't trace the link, so we exclude them from the list.
_EXTENSION_SEGMENTS = (
    '.GL.', '.GL32.', '.VulkanLayer.', '.ffmpeg', '.VAAPI.',
    '.openh264', '.Compat32.',
)


def _get_all_refs() -> dict[str, str]:
    """Return a dict mapping 'app_id/branch' (or 'app_id') -> full_ref for all installed flatpaks."""
    try:
        result = subprocess.run(
            ['flatpak', 'list', '--all', '--columns=ref'],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, 'LC_ALL': 'C', 'LANG': 'C'}
        )
        if result.returncode != 0:
            return {}
        refs: dict[str, str] = {}
        for line in result.stdout.splitlines():
            ref = line.strip()
            if '/' not in ref:
                continue
            parts = ref.split('/')
            app_id = parts[0]
            branch = parts[2] if len(parts) > 2 else ''
            key = f"{app_id}/{branch}" if branch else app_id
            refs[key] = ref
            # Also store just the app_id as fallback
            if app_id not in refs:
                refs[app_id] = ref
        return refs
    except Exception:
        return {}


def get_unused_flatpak_entries() -> list[FlatpakEntry]:
    """Return list of unused Flatpak runtimes using flatpak's own unused detection.

    Sends 'n' to stdin so the uninstall is cancelled after flatpak prints
    what it would remove — no data is actually deleted.

    Extensions used dynamically by gaming launchers (dxvk, gamescope, vkbasalt,
    MangoHud, etc.) are excluded because flatpak's resolver cannot trace those
    runtime dependencies.
    """
    if not flatpak_available():
        return []

    try:
        # flatpak uninstall --unused (without -y) prints a numbered table:
        #  1.  org.freedesktop.Platform    25.08    r
        # We feed 'n' so it cancels without removing anything.
        proc = subprocess.run(
            ['flatpak', 'uninstall', '--unused'],
            input='n\n',
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'LC_ALL': 'C', 'LANG': 'C'}
        )
        combined = proc.stdout + proc.stderr

        # Get all refs so we can look up the exact full ref (id/arch/branch)
        all_refs = _get_all_refs()

        unused_items: list[tuple[str, str]] = []  # list of (app_id, branch)
        for line in combined.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Table rows look like: "1.  org.freedesktop.Platform  25.08  r"
            # They always start with a number followed by a dot.
            tokens = stripped.split()
            if not tokens:
                continue
            first = tokens[0]
            if not (first[:-1].isdigit() and first.endswith('.')):
                continue
            if len(tokens) < 2:
                continue
            app_id = tokens[1]
            branch = tokens[2] if len(tokens) > 2 and tokens[2] != 'r' else ''
            
            # Skip graphics/vulkan/media extensions
            if any(seg in app_id for seg in _EXTENSION_SEGMENTS):
                continue
            unused_items.append((app_id, branch))

        entries = []
        for app_id, branch in unused_items:
            key = f"{app_id}/{branch}" if branch else app_id
            full_ref = all_refs.get(key, all_refs.get(app_id, f"{app_id}/x86_64/{branch}".strip('/')))
            
            parts = full_ref.split('/')
            arch = parts[1] if len(parts) > 1 else 'x86_64'
            
            size_bytes = _du_flatpak('runtime', app_id, arch, branch)
            entries.append(FlatpakEntry(ref=full_ref, name=app_id, size_bytes=size_bytes))

        return sorted(entries, key=lambda e: e.size_bytes, reverse=True)

    except Exception:
        return []


def _du_flatpak(kind: str, name: str, arch: str, branch: str) -> int:
    """Compute disk usage of a flatpak item via du -sb on its active directory."""
    for root in _FLATPAK_ROOTS:
        active = os.path.join(root, kind, name, arch, branch, 'active')
        # active is a symlink to the real commit directory — resolve it
        target = os.path.realpath(active) if os.path.islink(active) else active
        if os.path.isdir(target):
            try:
                du = subprocess.run(
                    ['du', '-sb', target],
                    capture_output=True, text=True, timeout=30
                )
                if du.returncode == 0 and du.stdout:
                    return int(du.stdout.split()[0])
            except Exception:
                pass
    return 0

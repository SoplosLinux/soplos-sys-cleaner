"""
Kernel scanning: detects installed kernels, headers, source and kbuild packages,
plus orphaned directories in /usr/src and /lib/modules.
The currently running kernel is always protected.
"""

import os
import re
import subprocess
import platform
from typing import NamedTuple


class KernelInfo(NamedTuple):
    version: str
    is_active: bool
    has_headers: bool
    has_src: bool
    has_kbuild: bool
    image_pkg: str
    headers_pkg: str
    src_pkg: str
    kbuild_pkg: str
    metapackage: str         # e.g. linux-soplos-gaming (empty if none found)
    size_kb: int
    orphan_src_dirs: list    # /usr/src dirs with no matching installed package
    orphan_modules_dirs: list  # /lib/modules dirs with no matching installed image


def get_current_kernel() -> str:
    """Returns the version string of the currently running kernel."""
    return platform.release()


def get_installed_kernels() -> list[KernelInfo]:
    """Returns a sorted list of installed kernels (newest first)."""
    current = get_current_kernel()
    kernels: dict[str, dict] = {}

    try:
        output = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${Package} ${Status}\n'],
            text=True
        )
        for line in output.splitlines():
            match = re.match(r'^(linux-image-(\S+))\s+install ok installed', line)
            if match:
                pkg = match.group(1)
                version = match.group(2)
                # Skip meta-packages (e.g. linux-image-amd64)
                if not re.match(r'^\d+\.\d+', version):
                    continue
                # Skip debug packages — they belong to the base kernel
                if version.endswith('-dbg'):
                    continue
                kernels[version] = {'image_pkg': pkg}
    except Exception as e:
        print(f'[kernels] Error querying packages: {e}')

    # Collect all installed kernel versions for orphan detection
    installed_versions = set(kernels.keys())

    result = []
    for version, info in kernels.items():
        headers_pkg  = f'linux-headers-{version}'
        src_pkg      = f'linux-source-{version}'
        # kbuild: matches linux-kbuild-X.Y (major.minor only)
        kbuild_ver   = _kbuild_version(version)
        kbuild_pkg   = f'linux-kbuild-{kbuild_ver}' if kbuild_ver else ''

        has_headers = _is_installed(headers_pkg)
        has_src     = _is_installed(src_pkg)
        has_kbuild  = bool(kbuild_pkg) and _is_installed(kbuild_pkg)

        size = _get_size(info['image_pkg'])
        if has_headers: size += _get_size(headers_pkg)
        if has_src:     size += _get_size(src_pkg)
        if has_kbuild:  size += _get_size(kbuild_pkg)

        orphan_src     = _orphan_src_dirs(version)
        orphan_modules = _orphan_modules_dirs(version)
        metapkg        = _find_metapackage(info['image_pkg'])

        result.append(KernelInfo(
            version=version,
            is_active=(version in current),
            has_headers=has_headers,
            has_src=has_src,
            has_kbuild=has_kbuild,
            image_pkg=info['image_pkg'],
            headers_pkg=headers_pkg if has_headers else '',
            src_pkg=src_pkg if has_src else '',
            kbuild_pkg=kbuild_pkg if has_kbuild else '',
            metapackage=metapkg,
            size_kb=size,
            orphan_src_dirs=orphan_src,
            orphan_modules_dirs=orphan_modules,
        ))

    # Sort: active first, then by version descending
    result.sort(key=lambda k: (not k.is_active, k.version), reverse=False)

    return result


def get_global_orphan_dirs() -> dict[str, list[str]]:
    """
    Finds /usr/src and /lib/modules directories that don't match any
    installed linux-image-* package — independently of the kernel list.
    Returns {'src': [...], 'modules': [...]}
    """
    installed = _get_installed_image_versions()
    return {
        'src': _find_unmatched_src_dirs(installed),
        'modules': _find_unmatched_modules_dirs(installed),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _kbuild_version(version: str) -> str:
    """Extracts X.Y from a kernel version string for linux-kbuild-X.Y."""
    match = re.match(r'^(\d+\.\d+)', version)
    return match.group(1) if match else ''


def _find_metapackage(image_pkg: str) -> str:
    """
    Returns the name of the installed metapackage (e.g. linux-soplos-gaming)
    that declares `image_pkg` as a dependency, or '' if none is found.

    Uses `apt-cache rdepends` to find reverse dependencies, then filters
    for packages that look like metapackages (no numeric version in name,
    starts with 'linux-') and are currently installed.
    """
    try:
        out = subprocess.check_output(
            ['apt-cache', 'rdepends', '--installed', image_pkg],
            stderr=subprocess.DEVNULL, text=True
        )
        for line in out.splitlines():
            line = line.strip()
            # apt-cache rdepends output: lines starting with a package name
            # prefixed with spaces; skip the header line
            if not line or line.startswith(image_pkg) or line.startswith('Reverse'):
                continue
            # Strip leading '|' or spaces
            candidate = line.lstrip('| ')
            if not candidate.startswith('linux-'):
                continue
            # Skip image/header/source packages — we want the pure metapackage
            if any(candidate.startswith(p) for p in (
                'linux-image-', 'linux-headers-', 'linux-source-',
                'linux-kbuild-', 'linux-compiler-'
            )):
                continue
            # Must be a real version number: reject names like linux-image-amd64
            # metapackages don't have numeric version segments in their name
            if re.search(r'-\d+\.\d+', candidate):
                continue
            if _is_installed(candidate):
                return candidate
    except Exception:
        pass
    return ''


def _is_installed(pkg: str) -> bool:
    try:
        result = subprocess.run(
            ['dpkg-query', '-W', '-f=${Status}', pkg],
            capture_output=True, text=True
        )
        return 'install ok installed' in result.stdout
    except Exception:
        return False


def _get_size(pkg: str) -> int:
    try:
        output = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${Installed-Size}', pkg],
            stderr=subprocess.DEVNULL, text=True
        )
        return int(output.strip() or 0)
    except Exception:
        return 0


def _get_installed_image_versions() -> set[str]:
    """Returns set of versions for all installed linux-image-* packages."""
    versions: set[str] = set()
    try:
        output = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${Package} ${Status}\n'], text=True
        )
        for line in output.splitlines():
            match = re.match(r'^linux-image-(\S+)\s+install ok installed', line)
            if match:
                v = match.group(1)
                if re.match(r'^\d+\.\d+', v) and not v.endswith('-dbg'):
                    versions.add(v)
    except Exception:
        pass
    return versions


def _orphan_src_dirs(version: str) -> list[str]:
    """
    Returns /usr/src dirs for this version that exist on disk but whose
    package is NOT installed (leftover after partial removal).
    """
    orphans = []
    src_base = '/usr/src'
    if not os.path.isdir(src_base):
        return orphans
    pattern = re.compile(r'^linux-headers-' + re.escape(version))
    for entry in os.scandir(src_base):
        if entry.is_dir() and pattern.match(entry.name):
            pkg = entry.name  # dir name matches package name
            if not _is_installed(pkg):
                orphans.append(entry.path)
    return orphans


def _orphan_modules_dirs(version: str) -> list[str]:
    """
    Returns /lib/modules dirs for this version that exist on disk but whose
    linux-image package is NOT installed.
    """
    orphans = []
    modules_base = '/lib/modules'
    if not os.path.isdir(modules_base):
        return orphans
    for entry in os.scandir(modules_base):
        if entry.is_dir() and entry.name.startswith(version):
            if not _is_installed(f'linux-image-{entry.name}'):
                orphans.append(entry.path)
    return orphans


def _find_unmatched_src_dirs(installed_versions: set[str]) -> list[str]:
    """Global scan: /usr/src/linux-headers-* dirs with no installed package."""
    orphans = []
    src_base = '/usr/src'
    if not os.path.isdir(src_base):
        return orphans
    for entry in os.scandir(src_base):
        if not entry.is_dir():
            continue
        match = re.match(r'^linux-headers-(\S+)', entry.name)
        if match:
            ver = match.group(1)
            base_ver = re.match(r'^(\d+\.\d+\.\d+-\d+)', ver)
            if base_ver and base_ver.group(1) not in installed_versions:
                if not _is_installed(entry.name):
                    orphans.append(entry.path)
    return orphans


def _find_unmatched_modules_dirs(installed_versions: set[str]) -> list[str]:
    """Global scan: /lib/modules dirs with no installed linux-image package."""
    orphans = []
    modules_base = '/lib/modules'
    if not os.path.isdir(modules_base):
        return orphans
    current = get_current_kernel()
    for entry in os.scandir(modules_base):
        if not entry.is_dir():
            continue
        if entry.name in current:
            continue  # never touch the running kernel's modules
        if not _is_installed(f'linux-image-{entry.name}'):
            orphans.append(entry.path)
    return orphans

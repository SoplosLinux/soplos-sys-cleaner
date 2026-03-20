"""
Kernel scanning: detects installed kernels, headers and source packages.
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
    image_pkg: str
    headers_pkg: str
    src_pkg: str
    size_kb: int


def get_current_kernel() -> str:
    """Returns the version string of the currently running kernel."""
    return platform.release()


def get_installed_kernels() -> list[KernelInfo]:
    """Returns a sorted list of installed kernels (newest first)."""
    current = get_current_kernel()
    kernels = {}

    try:
        output = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${Package} ${Status}\n'],
            text=True
        )
        # Match linux-image-X.Y.Z-N-arch packages
        for line in output.splitlines():
            match = re.match(r'^(linux-image-(\S+))\s+install ok installed', line)
            if match:
                pkg = match.group(1)
                version = match.group(2)
                # Skip meta-packages like linux-image-amd64
                if re.match(r'^\d+\.\d+', version):
                    kernels[version] = {'image_pkg': pkg}

    except Exception as e:
        print(f"[kernels] Error querying packages: {e}")

    # Now check headers and src for each version
    result = []
    for version, info in kernels.items():
        headers_pkg = f'linux-headers-{version}'
        src_pkg = f'linux-source-{version}'

        has_headers = _is_installed(headers_pkg)
        has_src = _is_installed(src_pkg)

        size = _get_size(info['image_pkg'])
        if has_headers:
            size += _get_size(headers_pkg)
        if has_src:
            size += _get_size(src_pkg)

        result.append(KernelInfo(
            version=version,
            is_active=(version in current),
            has_headers=has_headers,
            has_src=has_src,
            image_pkg=info['image_pkg'],
            headers_pkg=headers_pkg if has_headers else '',
            src_pkg=src_pkg if has_src else '',
            size_kb=size,
        ))

    # Sort: active first, then by version descending
    result.sort(key=lambda k: (not k.is_active, k.version), reverse=False)
    return result


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

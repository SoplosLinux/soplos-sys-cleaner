"""
Package query utilities (dpkg).
The detection logic of which packages to remove lives in scanner/hardware.py.
"""

import subprocess


def get_installed_size_kb(pkg_name: str) -> int:
    """Returns installed size of a package in KB."""
    try:
        output = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${Installed-Size}', pkg_name],
            stderr=subprocess.DEVNULL, text=True
        )
        return int(output.strip() or 0)
    except Exception:
        return 0


def get_package_description(pkg_name: str) -> str:
    """Returns short description of a package."""
    try:
        output = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${binary:Summary}', pkg_name],
            stderr=subprocess.DEVNULL, text=True
        )
        return output.strip()
    except Exception:
        return ''


def is_package_installed(pkg_name: str) -> bool:
    """Check if a package is installed."""
    try:
        result = subprocess.run(
            ['dpkg-query', '-W', '-f=${Status}', pkg_name],
            capture_output=True, text=True
        )
        return 'install ok installed' in result.stdout
    except Exception:
        return False

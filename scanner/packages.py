"""
Package scanning using dpkg and apt.
Maps GPU vendors to their unnecessary packages.
"""

import subprocess
from typing import NamedTuple


class PackageInfo(NamedTuple):
    name: str
    description: str
    installed_size: int  # KB
    vendor: str


# GPU vendor -> packages that can be removed if GPU not present
GPU_PACKAGE_MAP = {
    'NVIDIA': [
        'nvidia-driver', 'nvidia-driver-bin', 'nvidia-driver-libs',
        'nvidia-kernel-dkms', 'nvidia-kernel-support',
        'nvidia-alternative', 'nvidia-egl-icd',
        'libglx-nvidia0', 'libgl1-nvidia-glx', 'libnvidia-glcore',
        'libnvidia-encode1', 'libnvidia-cfg1', 'libnvidia-ml1',
        'libnvidia-fbc1', 'nvidia-vdpau-driver',
        'xserver-xorg-video-nvidia', 'nvidia-smi',
        'nvidia-settings', 'nvidia-modprobe', 'nvidia-persistenced',
        'nvidia-vulkan-icd', 'nvidia-nscq-525',
        'firmware-nvidia-graphics',
    ],
    'AMD': [
        'xserver-xorg-video-amdgpu',
        'xserver-xorg-video-ati',
        'xserver-xorg-video-radeon',
        'radeontop',
        # firmware-amd-graphics is omitted: it can be shared with APUs
    ],
    'INTEL': [
        'xserver-xorg-video-intel',
        'intel-media-va-driver',
        'intel-gpu-tools',
        'intel-opencl-icd',
    ],
    'VMWARE': [
        'xserver-xorg-video-vmware',
        'open-vm-tools', 'open-vm-tools-desktop',
    ],
}


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


def get_unnecessary_gpu_packages(current_vendors: list[str]) -> list[PackageInfo]:
    """
    Returns list of installed GPU packages for vendors NOT present in the system.
    """
    installed = []
    for vendor, packages in GPU_PACKAGE_MAP.items():
        if vendor in current_vendors:
            continue  # Skip: this GPU is present
        for pkg in packages:
            if is_package_installed(pkg):
                desc = get_package_description(pkg)
                size = get_installed_size_kb(pkg)
                installed.append(PackageInfo(
                    name=pkg,
                    description=desc,
                    installed_size=size,
                    vendor=vendor,
                ))
    return installed

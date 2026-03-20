"""
Hardware detection using lspci and lsusb.
Uses PCI Vendor IDs for accuracy.
"""

import os
import subprocess
import re

from utils.constants import PROTECTED_FIRMWARE_DIRS

# PCI Vendor IDs -> family name
GPU_VENDOR_IDS = {
    '10de': 'NVIDIA',
    '1002': 'AMD',
    '8086': 'INTEL',
    '15ad': 'VMWARE',
    '80ee': 'VIRTUALBOX',
}

PROTECTED_FIRMWARE = set(PROTECTED_FIRMWARE_DIRS)


def get_gpu_vendors() -> list[str]:
    """Returns list of detected GPU vendor names via lspci PCI IDs."""
    vendors = set()
    try:
        output = subprocess.check_output(['lspci', '-nn'], text=True, timeout=5)
        for line in output.splitlines():
            if 'VGA compatible controller' in line or '3D controller' in line:
                match = re.search(r'\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]', line)
                if match:
                    vendor_id = match.group(1).lower()
                    if vendor_id in GPU_VENDOR_IDS:
                        vendors.add(GPU_VENDOR_IDS[vendor_id])
                    else:
                        line_upper = line.upper()
                        if 'NVIDIA' in line_upper:
                            vendors.add('NVIDIA')
                        elif 'AMD' in line_upper or 'ATI' in line_upper:
                            vendors.add('AMD')
                        elif 'INTEL' in line_upper:
                            vendors.add('INTEL')
    except Exception as e:
        print(f"[hardware] Error detecting GPU: {e}")
    return list(vendors)


def get_all_firmware_families() -> list[str]:
    """Returns all firmware family directories found in /lib/firmware."""
    fw_path = '/lib/firmware'
    families = []
    if os.path.isdir(fw_path):
        for entry in os.scandir(fw_path):
            if entry.is_dir():
                families.append(entry.name)
    return sorted(families)


def is_firmware_protected(family_name: str) -> bool:
    """Returns True if the firmware family is protected (network/Wi-Fi)."""
    name_lower = family_name.lower()
    return any(protected in name_lower for protected in PROTECTED_FIRMWARE)

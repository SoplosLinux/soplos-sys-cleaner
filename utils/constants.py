"""Constants and shared utilities for Soplos Sys Cleaner."""


def fmt_size(size_bytes: int) -> str:
    """Format a byte count into a human-readable string."""
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024**3:.1f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024**2:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"

APPLICATION_NAME = "Soplos Sys Cleaner"
APPLICATION_ID = "org.soplos.sys-cleaner"
APPLICATION_VERSION = "1.0.2"

WINDOW_DEFAULT_WIDTH = 920
WINDOW_DEFAULT_HEIGHT = 600

# Firmware directories that are ALWAYS protected regardless of detected hardware.
# This list is intentionally minimal — hardware-specific protection is handled
# dynamically by scanner/hardware.py using lspci + lsusb + lsmod.
# Only include dirs with no clear vendor owner or critical system blobs.
PROTECTED_FIRMWARE_ALWAYS = [
    'regulatory.db',  # wireless regulatory database — always needed
]

# Legacy alias kept for any remaining references — points to the new constant
PROTECTED_FIRMWARE_DIRS = PROTECTED_FIRMWARE_ALWAYS

# System paths
FIRMWARE_PATH = '/lib/firmware'
KERNEL_PATH = '/boot'
APT_CACHE_PATH = '/var/cache/apt/archives'
TEMP_PATHS = ['/tmp', '/var/tmp']

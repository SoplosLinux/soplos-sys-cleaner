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
APPLICATION_VERSION = "1.0.0"

WINDOW_DEFAULT_WIDTH = 920
WINDOW_DEFAULT_HEIGHT = 600

# Network firmwares — NEVER removed (protected by soplos.conf)
PROTECTED_FIRMWARE_DIRS = [
    'rtlwifi', 'rtw88', 'rtw89',
    'ath10k', 'ath11k', 'ath12k',
    'brcm', 'mediatek', 'intel',
    'iwlwifi',
]

# System paths
FIRMWARE_PATH = '/lib/firmware'
KERNEL_PATH = '/boot'
APT_CACHE_PATH = '/var/cache/apt/archives'
TEMP_PATHS = ['/tmp', '/var/tmp']

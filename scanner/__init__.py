"""Scanner module for Soplos Sys Cleaner."""
from .hardware import (
    get_all_hardware,
    get_all_firmware_families,
    get_firmware_protection_set,
    is_firmware_dir_protected,
    get_unnecessary_hardware_packages,
)
from .packages import is_package_installed, get_package_description, get_installed_size_kb
from .kernels import get_installed_kernels, get_current_kernel
from .cache import get_apt_cache_info, get_autoremove_packages
from .temp_files import get_temp_entries
from .locales import get_locales_info, get_docs_summary

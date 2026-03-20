"""Scanner module for Soplos Sys Cleaner."""
from .hardware import get_gpu_vendors, get_all_firmware_families, is_firmware_protected
from .packages import get_unnecessary_gpu_packages
from .kernels import get_installed_kernels, get_current_kernel
from .cache import get_apt_cache_info, get_autoremove_packages
from .temp_files import get_temp_entries
from .locales import get_locales_info, get_docs_summary

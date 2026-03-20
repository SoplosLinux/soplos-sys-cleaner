"""Cleaner module for Soplos Sys Cleaner."""
from .remover import (
    purge_packages, clean_apt_cache, autoremove_packages,
    delete_temp_paths, rebuild_initrd
)

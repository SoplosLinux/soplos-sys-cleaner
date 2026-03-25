#!/usr/bin/env python3
"""
Root scan script: runs as root via pkexec, outputs JSON to stdout.
Covers everything that requires elevated privileges.
"""

import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    results = {}

    try:
        from scanner.hardware import get_gpu_vendors, get_all_firmware_families, is_firmware_protected
        results['gpu_vendors'] = get_gpu_vendors()
        results['firmware_families'] = get_all_firmware_families()
        # is_firmware_protected is a function — serialize as a set of protected names
        families = results['firmware_families']
        results['protected_firmware'] = [f for f in families if is_firmware_protected(f)]
    except Exception as e:
        results['firmware_families'] = []
        results['gpu_vendors'] = []
        results['protected_firmware'] = []

    try:
        from scanner.packages import get_unnecessary_gpu_packages
        pkgs = get_unnecessary_gpu_packages(results.get('gpu_vendors', []))
        results['unnecessary_pkgs'] = [
            {'name': p.name, 'installed_size': p.installed_size, 'description': p.description, 'vendor': p.vendor}
            for p in pkgs
        ]
    except Exception:
        results['unnecessary_pkgs'] = []

    try:
        from scanner.kernels import get_installed_kernels
        kernels = get_installed_kernels()
        results['kernels'] = [
            {'version': k.version, 'packages': list(k.packages),
             'size_kb': k.size_kb, 'is_active': k.is_active}
            for k in kernels
        ]
    except Exception:
        results['kernels'] = []

    try:
        from scanner.cache import get_apt_cache_info, get_autoremove_packages
        results['apt_cache'] = get_apt_cache_info()
        results['autoremove_pkgs'] = get_autoremove_packages()
    except Exception:
        results['apt_cache'] = {}
        results['autoremove_pkgs'] = []

    try:
        from scanner.temp_files import get_temp_entries
        entries = get_temp_entries(min_age_days=0.0)
        results['temp_entries'] = [
            {'path': e.path, 'size_bytes': e.size_bytes,
             'age_days': e.age_days, 'is_dir': e.is_dir}
            for e in entries
        ]
    except Exception:
        results['temp_entries'] = []

    try:
        from scanner.locales import get_locales_info, get_docs_summary
        desktop = os.environ.get('SOPLOS_DESKTOP', 'unknown')
        locales = get_locales_info(desktop)
        results['locales'] = [
            {'code': l.code, 'name': l.name, 'paths': list(l.paths),
             'size_kb': l.size_kb, 'category': l.category}
            for l in locales
        ]
        docs = get_docs_summary()
        results['docs_summary'] = [
            {'name': d.name, 'path': d.path, 'size_kb': d.size_kb, 'type': d.type}
            for d in docs
        ]
    except Exception:
        results['locales'] = []
        results['docs_summary'] = []

    try:
        from scanner.logs import get_varlog_entries, get_journald_info
        log_entries = get_varlog_entries()
        results['log_entries'] = [
            {'name': e.name, 'path': e.path, 'size_bytes': e.size_bytes}
            for e in log_entries
        ]
        jinfo = get_journald_info()
        results['journald'] = {
            'size_bytes': jinfo.size_bytes,
            'disk_usage_str': jinfo.disk_usage_str
        }
    except Exception:
        results['log_entries'] = []
        results['journald'] = {'size_bytes': 0, 'disk_usage_str': ''}

    print(json.dumps(results))


if __name__ == '__main__':
    main()

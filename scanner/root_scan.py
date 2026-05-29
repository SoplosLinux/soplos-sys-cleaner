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

    # ── Hardware detection (three layers: lspci + lsusb + lsmod/modinfo) ──
    try:
        from scanner.hardware import (
            get_all_hardware,
            get_firmware_protection_set,
            get_all_firmware_families,
            get_unnecessary_hardware_packages,
        )
        hw = get_all_hardware()
        results['pci_vendors'] = hw['pci_vendors']
        results['gpu_pci_vendors'] = hw['gpu_pci_vendors']
        results['usb_vendors'] = hw['usb_vendors']
        results['gpu_vendors_named'] = hw['gpu_vendors_named']
        results['kvm_present'] = hw['kvm_present']
        results['vm_guest_type'] = hw['vm_guest_type']
        results['dracut_fw_dirs'] = list(hw['dracut_fw_dirs'])
        # active_fw_files is a set — convert to list for JSON
        results['active_fw_files'] = list(hw['active_fw_files'])

        families = get_all_firmware_families()
        results['firmware_families'] = families

        protection_set = get_firmware_protection_set(hw)
        results['protection_set'] = list(protection_set)

    except Exception as e:
        print(f'[root_scan] hardware error: {e}', file=sys.stderr)
        results['pci_vendors'] = []
        results['gpu_pci_vendors'] = []
        results['usb_vendors'] = []
        results['gpu_vendors_named'] = []
        results['kvm_present'] = False
        results['vm_guest_type'] = 'none'
        results['dracut_fw_dirs'] = []
        results['active_fw_files'] = []
        results['firmware_families'] = []
        results['protection_set'] = []

    # ── Unnecessary hardware packages ──
    try:
        from scanner.hardware import get_unnecessary_hardware_packages
        pkgs = get_unnecessary_hardware_packages(
            results.get('pci_vendors', []),
            results.get('usb_vendors', []),
            results.get('kvm_present', False),
            gpu_pci_vendors=results.get('gpu_pci_vendors', []),
            vm_guest_type=results.get('vm_guest_type', 'none'),
        )
        results['unnecessary_pkgs'] = pkgs
    except Exception as e:
        print(f'[root_scan] packages error: {e}', file=sys.stderr)
        results['unnecessary_pkgs'] = []

    # ── Kernels ──
    try:
        from scanner.kernels import get_installed_kernels
        kernels = get_installed_kernels()
        results['kernels'] = [
            {
                'version': k.version,
                'packages': list(k.packages),
                'size_kb': k.size_kb,
                'is_active': k.is_active,
                'image_pkg': k.image_pkg,
                'headers_pkg': k.headers_pkg,
                'src_pkg': k.src_pkg,
                'kbuild_pkg': k.kbuild_pkg,
                'has_headers': k.has_headers,
                'has_src': k.has_src,
                'has_kbuild': k.has_kbuild,
                'orphan_src_dirs': k.orphan_src_dirs,
                'orphan_modules_dirs': k.orphan_modules_dirs,
            }
            for k in kernels
        ]
    except Exception as e:
        print(f'[root_scan] kernels error: {e}', file=sys.stderr)
        results['kernels'] = []

    # ── APT cache ──
    try:
        from scanner.cache import get_apt_cache_info, get_autoremove_packages
        results['apt_cache'] = get_apt_cache_info()
        results['autoremove_pkgs'] = get_autoremove_packages()
    except Exception:
        results['apt_cache'] = {}
        results['autoremove_pkgs'] = []

    # ── Temp files ──
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

    # ── Locales & docs ──
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

    # ── System logs ──
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

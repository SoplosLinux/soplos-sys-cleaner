#!/usr/bin/env python3
"""
Persistent root helper: launched once via pkexec, receives JSON commands on stdin,
returns JSON results on stdout. Eliminates repeated password prompts.
"""

import sys
import os
import json
import shutil
import shlex
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── Scan ────────────────────────────────────────────────────────────────────

def do_scan(params):
    results = {}

    # Hardware detection: three layers (lspci + lsusb + lsmod/modinfo)
    try:
        from scanner.hardware import (
            get_all_hardware,
            get_firmware_protection_set,
            get_all_firmware_families,
            get_firmware_sizes,
            get_unnecessary_hardware_packages,
        )
        hw = get_all_hardware()
        results['dracut_fw_dirs']    = list(hw['dracut_fw_dirs'])
        results['pci_vendors']       = hw['pci_vendors']
        results['usb_vendors']       = hw['usb_vendors']
        results['gpu_vendors_named'] = hw['gpu_vendors_named']
        results['kvm_present']       = hw['kvm_present']
        results['vm_guest_type']     = hw.get('vm_guest_type', 'none')
        results['active_fw_files']   = list(hw['active_fw_files'])

        families = get_all_firmware_families()
        results['firmware_families'] = families
        results['firmware_sizes']    = get_firmware_sizes(families)

        protection_set = get_firmware_protection_set(hw)
        results['protection_set'] = list(protection_set)

        pkgs = get_unnecessary_hardware_packages(
            hw['pci_vendors'], hw['usb_vendors'], hw['kvm_present']
        )
        results['unnecessary_pkgs'] = pkgs

        # hardware_summary for Drivers tab label
        vm_type = hw.get('vm_guest_type', 'none')
        _VM_LABELS = {
            'kvm':       'KVM/QEMU (guest)',
            'qemu':      'QEMU (guest)',
            'vmware':    'VMware (guest)',
            'oracle':    'VirtualBox (guest)',
            'microsoft': 'Hyper-V (guest)',
            'xen':       'Xen (guest)',
            'parallels': 'Parallels (guest)',
            'bhyve':     'bhyve (guest)',
        }
        summary = list(hw['gpu_vendors_named'])
        if hw['kvm_present']:
            summary.append('KVM host')
        if vm_type not in ('none', '') and vm_type in _VM_LABELS:
            vm_label = _VM_LABELS[vm_type]
            if vm_label not in summary:
                summary.append(vm_label)
        results['hardware_summary'] = summary
    except Exception as e:
        print(f'[root_helper] hardware error: {e}', file=sys.stderr)
        results['pci_vendors']       = []
        results['usb_vendors']       = []
        results['gpu_vendors_named'] = []
        results['kvm_present']       = False
        results['vm_guest_type']     = 'none'
        results['active_fw_files']   = []
        results['firmware_families'] = []
        results['firmware_sizes']    = {}
        results['protection_set']    = []
        results['unnecessary_pkgs']  = []
        results['hardware_summary']  = []

    # Kernels
    try:
        from scanner.kernels import get_installed_kernels
        kernels = get_installed_kernels()
        results['kernels'] = [
            {
                'version': k.version, 'is_active': k.is_active,
                'has_headers': k.has_headers, 'has_src': k.has_src,
                'has_kbuild': k.has_kbuild,
                'image_pkg': k.image_pkg, 'headers_pkg': k.headers_pkg,
                'src_pkg': k.src_pkg, 'kbuild_pkg': k.kbuild_pkg,
                'metapackage': k.metapackage,
                'size_kb': k.size_kb,
                'orphan_src_dirs': k.orphan_src_dirs,
                'orphan_modules_dirs': k.orphan_modules_dirs,
            }
            for k in kernels
        ]
    except Exception as e:
        print(f'[root_helper] kernels error: {e}', file=sys.stderr)
        results['kernels'] = []

    # APT cache
    try:
        from scanner.cache import get_apt_cache_info, get_autoremove_packages, get_apt_cache_debs
        results['apt_cache']      = get_apt_cache_info()
        results['apt_cache_debs'] = get_apt_cache_debs()
        results['autoremove_pkgs'] = get_autoremove_packages()
    except Exception:
        results['apt_cache']       = {}
        results['autoremove_pkgs'] = []

    # Temp files
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

    # Locales & docs
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
        results['locales']      = []
        results['docs_summary'] = []

    # System logs
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
            'disk_usage_str': jinfo.disk_usage_str,
        }
    except Exception:
        results['log_entries'] = []
        results['journald']    = {'size_bytes': 0, 'disk_usage_str': ''}

    return results


# ─── Clean actions ───────────────────────────────────────────────────────────

def do_delete_paths(params):
    paths = params.get('paths', [])
    errors = []
    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            errors.append(str(e))
    return {'success': len(errors) == 0, 'error': ' | '.join(errors) if errors else None}


def do_apt_clean(params):
    result = subprocess.run(['apt', 'clean'], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_apt_autoremove(params):
    result = subprocess.run(['apt', 'autoremove', '-y'], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_apt_purge(params):
    packages         = params.get('packages', [])
    rebuild          = params.get('rebuild_initrd', False)
    update_bootloader = params.get('update_bootloader', False)
    pkg_str  = ' '.join(shlex.quote(p) for p in packages)
    cmds = [
        f'apt purge -y {pkg_str}',
        'apt autoremove -y',
    ]
    if rebuild:
        cmds.append('dracut -f')
    if update_bootloader:
        cmds.append('update-grub')
    result = subprocess.run(['bash', '-c', ' && '.join(cmds)], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_vacuum_journal(params):
    flag   = params.get('flag', '--vacuum-size=100M')
    result = subprocess.run(['journalctl', flag], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_delete_locales(params):
    paths      = params.get('paths', [])
    keep_codes = params.get('keep_codes', [])
    errors     = []

    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            errors.append(str(e))

    if keep_codes:
        if not shutil.which('localepurge'):
            subprocess.run(
                ['bash', '-c', 'DEBIAN_FRONTEND=noninteractive apt install -y localepurge'],
                capture_output=True, text=True
            )
        codes   = sorted(set(keep_codes))
        nopurge = (
            '# Generated by Soplos Sys Cleaner\n'
            'NEEDSCONFIGUPDATE=0\nVERBOSE=0\nSHOWFREEDSPACE=1\nDONTBOTHERNEWLOCALE\n'
        )
        nopurge += ''.join(f'{c}\n' for c in codes)
        try:
            with open('/etc/locale.nopurge', 'w') as f:
                f.write(nopurge)
            lp = '/usr/sbin/localepurge' if os.path.exists('/usr/sbin/localepurge') else shutil.which('localepurge')
            if lp:
                subprocess.run([lp], capture_output=True, text=True)
        except Exception as e:
            errors.append(str(e))

    return {'success': len(errors) == 0, 'error': ' | '.join(errors) if errors else None}


def do_delete_docs(params):
    """Remove documentation paths only — does NOT invoke localepurge."""
    paths  = params.get('paths', [])
    errors = []
    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            errors.append(str(e))
    return {'success': len(errors) == 0, 'error': ' | '.join(errors) if errors else None}


def do_remove_firmware(params):
    families = params.get('families', [])
    errors   = []
    for family in families:
        path = f'/lib/firmware/{family}'
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            errors.append(str(e))
    result = subprocess.run(['dracut', '-f'], capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(result.stderr.strip())
    return {'success': len(errors) == 0, 'error': ' | '.join(errors) if errors else None}


def do_delete_orphan_dirs(params):
    """Remove orphaned kernel dirs (/usr/src/linux-headers-*, /lib/modules/*)."""
    paths  = params.get('paths', [])
    errors = []
    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            errors.append(str(e))
    return {'success': len(errors) == 0, 'error': ' | '.join(errors) if errors else None}


# ─── Dispatch ─────────────────────────────────────────────────────────────────

HANDLERS = {
    'scan':               do_scan,
    'delete_paths':       do_delete_paths,
    'apt_clean':          do_apt_clean,
    'apt_autoremove':     do_apt_autoremove,
    'apt_purge':          do_apt_purge,
    'vacuum_journal':     do_vacuum_journal,
    'delete_locales':     do_delete_locales,
    'delete_docs':        do_delete_docs,
    'remove_firmware':    do_remove_firmware,
    'delete_orphan_dirs': do_delete_orphan_dirs,
}


def _clean_pycache():
    try:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            if '__pycache__' in dirs:
                shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
                if '__pycache__' in dirs:
                    dirs.remove('__pycache__')
    except Exception:
        pass


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd     = json.loads(line)
            action  = cmd.get('action')
            if action == 'exit':
                _clean_pycache()
                break
            handler = HANDLERS.get(action)
            result  = handler(cmd) if handler else {'error': f'Unknown action: {action}'}
        except Exception as e:
            result = {'error': str(e)}
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

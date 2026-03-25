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

    try:
        from scanner.hardware import get_gpu_vendors, get_all_firmware_families, is_firmware_protected
        results['gpu_vendors'] = get_gpu_vendors()
        results['firmware_families'] = get_all_firmware_families()
        results['protected_firmware'] = [f for f in results['firmware_families'] if is_firmware_protected(f)]
    except Exception:
        results['gpu_vendors'] = []
        results['firmware_families'] = []
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
            {'version': k.version, 'is_active': k.is_active,
             'has_headers': k.has_headers, 'has_src': k.has_src,
             'image_pkg': k.image_pkg, 'headers_pkg': k.headers_pkg,
             'src_pkg': k.src_pkg, 'size_kb': k.size_kb}
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
    return {'success': len(errors) == 0, 'error': " | ".join(errors) if errors else None}


def do_apt_clean(params):
    result = subprocess.run(['apt-get', 'clean'], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_apt_autoremove(params):
    result = subprocess.run(['apt-get', 'autoremove', '-y'], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_apt_purge(params):
    packages = params.get('packages', [])
    rebuild = params.get('rebuild_initrd', False)
    pkg_str = ' '.join(shlex.quote(p) for p in packages)
    cmds = [f'apt-get purge -y --allow-remove-essential=false {pkg_str}', 'apt-get autoremove -y']
    if rebuild:
        cmds.append('dracut -f')
    result = subprocess.run(['bash', '-c', ' && '.join(cmds)], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_vacuum_journal(params):
    flag = params.get('flag', '--vacuum-size=100M')
    result = subprocess.run(['journalctl', flag], capture_output=True, text=True)
    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


def do_delete_locales(params):
    paths = params.get('paths', [])
    keep_codes = params.get('keep_codes', [])
    errors = []

    # Delete selected paths
    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            errors.append(str(e))

    # Configure localepurge
    if keep_codes:
        if not shutil.which('localepurge'):
            subprocess.run(
                ['bash', '-c', 'DEBIAN_FRONTEND=noninteractive apt-get install -y localepurge'],
                capture_output=True, text=True
            )
        codes = sorted(set(keep_codes))
        nopurge = "# Generated by Soplos Sys Cleaner\nNEEDSCONFIGUPDATE=0\nVERBOSE=0\nSHOWFREEDSPACE=1\nDONTBOTHERNEWLOCALE\n"
        nopurge += ''.join(f'{c}\n' for c in codes)
        try:
            with open('/etc/locale.nopurge', 'w') as f:
                f.write(nopurge)
            
            localepurge_bin = '/usr/sbin/localepurge' if os.path.exists('/usr/sbin/localepurge') else shutil.which('localepurge')
            if localepurge_bin:
                subprocess.run([localepurge_bin], capture_output=True, text=True)
        except Exception as e:
            errors.append(str(e))

    return {'success': len(errors) == 0, 'error': " | ".join(errors) if errors else None}


def do_remove_firmware(params):
    families = params.get('families', [])
    paths = [f'/lib/firmware/{f}' for f in families]
    errors = []
    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            errors.append(str(e))
    result = subprocess.run(['dracut', '-f'], capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(result.stderr.strip())
    return {'success': len(errors) == 0, 'error': " | ".join(errors) if errors else None}


# ─── Dispatch ─────────────────────────────────────────────────────────────────

HANDLERS = {
    'scan':            do_scan,
    'delete_paths':    do_delete_paths,
    'apt_clean':       do_apt_clean,
    'apt_autoremove':  do_apt_autoremove,
    'apt_purge':       do_apt_purge,
    'vacuum_journal':  do_vacuum_journal,
    'delete_locales':  do_delete_locales,
    'remove_firmware': do_remove_firmware,
}


def _clean_pycache():
    """Recursively remove __pycache__ directories in PROJECT_ROOT."""
    try:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            if '__pycache__' in dirs:
                shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
                # Prevent os.walk from entering the directory we just deleted
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
            cmd = json.loads(line)
            action = cmd.get('action')
            if action == 'exit':
                _clean_pycache()
                break
            handler = HANDLERS.get(action)
            result = handler(cmd) if handler else {'error': f'Unknown action: {action}'}
        except Exception as e:
            result = {'error': str(e)}
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

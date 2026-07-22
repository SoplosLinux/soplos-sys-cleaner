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
        results['gpu_pci_vendors']   = hw['gpu_pci_vendors']
        results['network_pci_vendors'] = hw['network_pci_vendors']
        results['audio_pci_vendors']    = hw['audio_pci_vendors']
        results['usb_vendors']       = hw['usb_vendors']
        results['gpu_vendors_named'] = hw['gpu_vendors_named']
        results['kvm_present']       = hw['kvm_present']
        results['vm_guest_type']     = hw.get('vm_guest_type', 'none')
        results['active_fw_files']   = list(hw['active_fw_files'])

        families = get_all_firmware_families()
        results['firmware_families'] = families
        results['firmware_sizes']    = get_firmware_sizes(families)

        from scanner.hardware import get_firmware_owning_packages
        results['firmware_owning_pkg'] = get_firmware_owning_packages(families)

        protection_set = get_firmware_protection_set(hw)
        results['protection_set'] = list(protection_set)

        from scanner.hardware import get_orphan_dkms_modules
        results['orphan_dkms'] = get_orphan_dkms_modules()

        pkgs = get_unnecessary_hardware_packages(
            hw['pci_vendors'],
            hw['usb_vendors'],
            hw['kvm_present'],
            gpu_pci_vendors=hw['gpu_pci_vendors'],
            vm_guest_type=hw.get('vm_guest_type', 'none'),
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
        results['orphan_dkms']       = []
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
        from scanner.cache import get_apt_cache_info, get_autoremove_packages, get_apt_cache_debs, get_orphan_module_refs
        results['apt_cache']          = get_apt_cache_info()
        results['apt_cache_debs']     = get_apt_cache_debs()
        results['autoremove_pkgs']    = get_autoremove_packages()
        results['orphan_module_refs'] = get_orphan_module_refs(
            vm_guest_type=results.get('vm_guest_type', 'none')
        )
    except Exception:
        results['apt_cache']          = {}
        results['autoremove_pkgs']    = []
        results['orphan_module_refs'] = []

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
    packages          = params.get('packages', [])
    rebuild           = params.get('rebuild_initrd', False)
    update_bootloader = params.get('update_bootloader', False)
    pkg_str = ' '.join(shlex.quote(p) for p in packages)
    cmds = [
        f'apt purge -y {pkg_str}',
        'apt autoremove -y',
    ]
    if rebuild:
        cmds.append('dracut -f')
    if update_bootloader:
        cmds.append('update-grub')

    result = subprocess.run(['bash', '-c', ' && '.join(cmds)], capture_output=True, text=True)

    if rebuild:
        _cleanup_module_references(packages)

    return {'success': result.returncode == 0, 'stderr': result.stderr.strip()}


# Single source of truth for package -> kernel module(s): scanner/hardware.py
from scanner.hardware import PKG_MODULES


def _remove_module_entries(modules: set):
    """Remove entries for the given module names from /etc/modules and /etc/modules-load.d/."""
    if not modules:
        return

    def _clean_file(path):
        try:
            with open(path) as f:
                lines = f.readlines()
            cleaned = [l for l in lines if l.strip().lstrip('#').strip() not in modules]
            if len(cleaned) == len(lines):
                return
            remaining = [l for l in cleaned if l.strip() and not l.strip().startswith('#')]
            if not remaining:
                os.remove(path)
            else:
                with open(path, 'w') as f:
                    f.writelines(cleaned)
        except Exception:
            pass

    if os.path.isfile('/etc/modules'):
        _clean_file('/etc/modules')

    modules_load_dir = '/etc/modules-load.d'
    if os.path.isdir(modules_load_dir):
        for fname in os.listdir(modules_load_dir):
            _clean_file(os.path.join(modules_load_dir, fname))


def _cleanup_module_references(packages: list[str]):
    """Resolve package names to module names and clean their references."""
    modules = set()
    for pkg in packages:
        modules.update(PKG_MODULES.get(pkg, []))
    _remove_module_entries(modules)


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

    from scanner.hardware import PCI_VENDOR_FIRMWARE, PCI_VENDOR_PACKAGES

    # Map of firmware directory names → owning "firmware-only" APT package.
    # Packages marked 'generic' (firmware-linux-nonfree, firmware-misc-nonfree)
    # bundle many unrelated hardware families and cannot be safely purged;
    # their files are deleted directly instead.
    FIRMWARE_PACKAGES = {
        # AMD GPU
        'amdgpu':   'firmware-amd-graphics',
        'radeon':   'firmware-amd-graphics',
        # Intel GPU
        'i915':     'firmware-intel-graphics',
        # Intel WiFi
        'iwlwifi':  'firmware-iwlwifi',
        # Intel sound / DSP (separate package)
        'intel':    'firmware-intel-sound',
        # Realtek WiFi / Bluetooth
        'rtlwifi':  'firmware-realtek',
        'rtw88':    'firmware-realtek',
        'rtw89':    'firmware-realtek',
        'rtl_bt':   'firmware-realtek',
        'rtl8761b': 'firmware-realtek',
        'rtl8821c': 'firmware-realtek',
        'rtl8822c': 'firmware-realtek',
        'rtl8852a': 'firmware-realtek',
        'rtl8852b': 'firmware-realtek',
        'rtl8852c': 'firmware-realtek',
        'rtl_nic':  'firmware-realtek',
        # Broadcom WiFi / Bluetooth
        'brcm':     'firmware-brcm80211',
        # Qualcomm / Atheros WiFi
        'ath10k':   'firmware-atheros',
        'ath11k':   'firmware-atheros',
        'ath12k':   'firmware-atheros',
        'qca':      'firmware-atheros',
        # MediaTek WiFi
        'mediatek': 'firmware-mediatek',
        'mt76':     'firmware-mediatek',
        # Marvell WiFi / network
        'libertas': 'firmware-libertas',
        'mwl8k':    'firmware-libertas',
        'mwifiex':  'firmware-libertas',
        # NVIDIA GPU
        'nvidia':   'firmware-nvidia-graphics',
    }

    # Packages that bundle many unrelated hardware families — purging them
    # would remove firmware for hardware the user may have.  Delete dirs only.
    GENERIC_PACKAGES = {
        'firmware-linux-nonfree',
        'firmware-misc-nonfree',
        'firmware-linux',
        'firmware-linux-free',
    }

    # Firmware family → full driver package stack (kernel modules, dkms, xorg
    # driver...), on top of the firmware-only package above. Without this, a
    # family like 'nvidia' could have its firmware directory deleted while
    # firmware-nvidia-graphics is not installed (the driver was pulled in via
    # the bigger nvidia-driver package instead) — files gone, driver still
    # fully installed. Reuses hardware.py's vendor→package map so this stays
    # in sync with the Drivers tab instead of duplicating package names here.
    _family_vendor: dict[str, str] = {}
    for vendor_id, fams in PCI_VENDOR_FIRMWARE.items():
        for fam in fams:
            _family_vendor[fam] = vendor_id
    DRIVER_PACKAGES: dict[str, list[str]] = {
        fam: PCI_VENDOR_PACKAGES[vid]
        for fam, vid in _family_vendor.items()
        if vid in PCI_VENDOR_PACKAGES
    }

    # Every package (firmware or driver) mapped to the full set of firmware
    # families it is associated with, across the whole map — not just the
    # families selected for removal — so we can tell whether purging it would
    # also affect firmware the user did NOT select.
    PACKAGE_ALL_FAMILIES: dict[str, set[str]] = {}
    for fam, pkg in FIRMWARE_PACKAGES.items():
        if pkg not in GENERIC_PACKAGES:
            PACKAGE_ALL_FAMILIES.setdefault(pkg, set()).add(fam)
    for fam, pkgs in DRIVER_PACKAGES.items():
        for pkg in pkgs:
            PACKAGE_ALL_FAMILIES.setdefault(pkg, set()).add(fam)

    def _is_installed(pkg):
        try:
            r = subprocess.run(
                ['dpkg-query', '-W', '-f=${Status}', pkg],
                capture_output=True, text=True, timeout=5
            )
            return 'install ok installed' in r.stdout
        except Exception:
            return False

    selected = set(families)

    # Packages potentially touched by this removal: firmware-only + full
    # driver stack for every selected family.
    candidate_pkgs: set[str] = set()
    for fam in selected:
        fw_pkg = FIRMWARE_PACKAGES.get(fam)
        if fw_pkg and fw_pkg not in GENERIC_PACKAGES:
            candidate_pkgs.add(fw_pkg)
        candidate_pkgs.update(DRIVER_PACKAGES.get(fam, []))

    for pkg in candidate_pkgs:
        if not _is_installed(pkg):
            continue
        owned_families = PACKAGE_ALL_FAMILIES.get(pkg, set())
        existing_owned = {f for f in owned_families if os.path.isdir(f'/lib/firmware/{f}')}
        if existing_owned and existing_owned.issubset(selected):
            # Every firmware family this package owns is being removed —
            # safe to purge the whole package (firmware + driver together).
            result = subprocess.run(['apt', 'purge', '-y', pkg], capture_output=True, text=True)
            if result.returncode != 0:
                errors.append(f'apt purge {pkg}: {result.stderr.strip()}')
        # else: this package also owns firmware for a family that was NOT
        # selected — leave it installed, only the selected dirs get wiped below.

    # Delete whatever remains on disk for every selected family: manually
    # installed files with no owning package, and any package left installed
    # above because it also serves an unselected family.
    for family in selected:
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


def _clean_module_refs_action(params):
    refs    = params.get('refs', [])
    errors  = []

    module_refs   = [r for r in refs if r.get('type') in ('modules-load', 'modprobe')]
    systemd_refs  = [r for r in refs if r.get('type') == 'systemd']
    autostart_refs = [r for r in refs if r.get('type') == 'autostart']

    # VirtualBox Guest Additions installed via the official .run installer
    # (VBoxLinuxAdditions.run) are never tracked by dpkg — there is no
    # package to purge, so the generic per-file cleanup below can only ever
    # remove the systemd unit and the X11 autostart script, leaving the
    # kernel modules, DKMS entries and /opt/VBoxGuestAdditions-*/ payload
    # fully installed. Run the official uninstaller first when present: it
    # correctly tears down modules, DKMS, systemd units and X11 configs in
    # one shot. Whatever it doesn't cover still falls through to the manual
    # cleanup below (idempotent — os.remove is skipped if already gone).
    VBOX_SYSTEMD_UNITS   = {'vboxadd.service', 'vboxadd-service.service', 'vbox-guest-utils.service'}
    VBOX_AUTOSTART_NAMES = {'98vboxadd-xclient', 'vboxclient.desktop'}
    is_vbox_ref = (
        any(r.get('type') == 'systemd' and r.get('module') in VBOX_SYSTEMD_UNITS for r in refs) or
        any(r.get('type') == 'autostart' and r.get('module') in VBOX_AUTOSTART_NAMES for r in refs)
    )
    if is_vbox_ref:
        import glob
        uninstaller = next(iter(sorted(
            glob.glob('/opt/VBoxGuestAdditions-*/uninstall.sh'), reverse=True
        )), None)
        if uninstaller and os.access(uninstaller, os.X_OK):
            result = subprocess.run([uninstaller], capture_output=True, text=True)
            if result.returncode != 0:
                errors.append(f'VBoxGuestAdditions uninstall.sh: {result.stderr.strip() or result.stdout.strip()}')
        else:
            rcvboxadd = shutil.which('rcvboxadd') or (
                '/sbin/rcvboxadd' if os.path.exists('/sbin/rcvboxadd') else None
            )
            if rcvboxadd:
                subprocess.run([rcvboxadd, 'cleanup'], capture_output=True, text=True)

    # Clean module load files
    modules = {r['module'] for r in module_refs}
    _remove_module_entries(modules)

    # Remove orphaned modprobe.d files entirely if they only reference uninstalled modules
    modprobe_paths = {r['path'] for r in refs if r.get('type') == 'modprobe'}
    for path in modprobe_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            errors.append(str(e))

    # Disable and remove orphaned systemd services (no-op if the VBox
    # uninstaller above already removed the unit)
    for ref in systemd_refs:
        svc  = ref['module']
        path = ref['path']
        subprocess.run(['systemctl', 'disable', '--now', svc],
                       capture_output=True, text=True)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            errors.append(str(e))
    if systemd_refs:
        subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, text=True)

    # Remove orphaned X11/XDG autostart files (no-op if already removed above)
    for ref in autostart_refs:
        try:
            if os.path.exists(ref['path']):
                os.remove(ref['path'])
        except Exception as e:
            errors.append(str(e))

    # Remove orphaned /etc/dracut.conf.d/*.conf left by driver installers.
    # Hard safety net: never delete distro-policy confs, even if a future
    # detection bug in cache.py ever flagged one of these by mistake.
    NEVER_TOUCH_DRACUT_CONFS = {'soplos.conf', 'i18n.conf', 'local.conf'}
    dracut_refs = [r for r in refs if r.get('type') == 'dracut']
    for ref in dracut_refs:
        path = ref['path']
        if os.path.basename(path) in NEVER_TOUCH_DRACUT_CONFS:
            continue
        try:
            os.remove(path)
        except Exception as e:
            errors.append(str(e))

    result = subprocess.run(['dracut', '-f'], capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(result.stderr.strip())

    return {'success': len(errors) == 0, 'stderr': ' | '.join(errors)}


def do_remove_dkms_orphans(params):
    """Remove orphaned DKMS module trees and rebuild initramfs."""
    orphans = params.get('orphans', [])
    errors  = []

    for orphan in orphans:
        name     = orphan.get('name', '')
        version  = orphan.get('version', '')
        dkms_dir = orphan.get('dkms_dir', '')

        # Try dkms remove first; fall back to direct deletion
        result = subprocess.run(
            ['dkms', 'remove', f'{name}/{version}', '--all'],
            capture_output=True, text=True
        )
        if result.returncode != 0 and dkms_dir and os.path.isdir(dkms_dir):
            try:
                import shutil
                shutil.rmtree(dkms_dir)
            except Exception as e:
                errors.append(str(e))

    # Rebuild module dependencies and initramfs
    subprocess.run(['depmod', '-a'], capture_output=True, text=True)
    result = subprocess.run(['dracut', '-f'], capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(result.stderr.strip())

    return {'success': len(errors) == 0, 'stderr': ' | '.join(errors)}


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
    'delete_orphan_dirs':   do_delete_orphan_dirs,
    'remove_dkms_orphans':  do_remove_dkms_orphans,
    'clean_module_refs':    lambda p: _clean_module_refs_action(p),
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


def _remove_stale_root_desktop():
    """
    A previous version dropped an "Administrator" .desktop launcher at
    runtime (soplos-sys-cleaner --root, since removed — it never worked
    reliably). soplos-packager doesn't support postinst maintainer scripts,
    so the leftover file can't be cleaned up at package-upgrade time; clean
    it up here instead, the first time a root session starts after the
    upgrade, since this process already runs as root anyway.
    """
    try:
        os.remove('/usr/share/applications/org.soplos.sys-cleaner-root.desktop')
    except FileNotFoundError:
        pass
    except Exception:
        pass


def main():
    _remove_stale_root_desktop()
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

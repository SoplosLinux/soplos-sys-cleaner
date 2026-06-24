"""
APT cache scanner: measures cache size and orphaned packages.
"""

import os
import subprocess


def get_apt_cache_info() -> dict:
    """Returns APT cache size (.deb files) and apt lists size."""
    cache_path = '/var/cache/apt/archives'
    total_size = 0
    deb_count = 0

    if os.path.isdir(cache_path):
        for entry in os.scandir(cache_path):
            if entry.is_file() and entry.name.endswith('.deb'):
                try:
                    total_size += entry.stat().st_size
                    deb_count += 1
                except OSError:
                    pass

    lists_path = '/var/lib/apt/lists'
    lists_size = 0
    if os.path.isdir(lists_path):
        for entry in os.scandir(lists_path):
            if entry.is_file():
                try:
                    lists_size += entry.stat().st_size
                except OSError:
                    pass

    return {
        'path': cache_path,
        'size_bytes': total_size,
        'deb_count': deb_count,
        'lists_size_bytes': lists_size,
    }


def get_apt_cache_debs() -> list[dict]:
    """Returns individual .deb files in the APT cache with name and size."""
    cache_path = '/var/cache/apt/archives'
    debs = []
    if os.path.isdir(cache_path):
        for entry in os.scandir(cache_path):
            if entry.is_file() and entry.name.endswith('.deb'):
                try:
                    debs.append({'name': entry.name, 'path': entry.path, 'size_bytes': entry.stat().st_size})
                except OSError:
                    pass
    return sorted(debs, key=lambda d: d['size_bytes'], reverse=True)


def get_orphan_module_refs(vm_guest_type: str = 'none') -> list[dict]:
    """
    Finds leftover references to kernel modules / services from packages
    that are no longer installed. Checks:
      - /etc/modules
      - /etc/modules-load.d/
      - /etc/modprobe.d/
      - systemd unit files for known VM guest services
    Returns list of {'module', 'source', 'path', 'type'}

    vm_guest_type: result of systemd-detect-virt — files belonging to the
    current guest platform are never flagged as orphans, even when the apt
    package is absent (Guest Additions installed from the hypervisor ISO).
    """
    # Packages that belong to each hypervisor guest platform.
    # All packages for the current guest type are protected.
    GUEST_PLATFORM_PKGS: dict[str, list[str]] = {
        'oracle': [
            'virtualbox-guest-utils', 'virtualbox-guest-dkms',
            'virtualbox-guest-x11',
        ],
        'vmware': [
            'open-vm-tools', 'open-vm-tools-desktop',
        ],
        'microsoft': [
            'hyperv-daemons',
        ],
        'kvm': [
            'spice-vdagent', 'spice-webdavd',
        ],
        'qemu': [
            'spice-vdagent', 'spice-webdavd',
        ],
    }
    # kvm and qemu are aliases
    VM_GUEST_ALIASES: dict[str, str] = {'kvm': 'qemu', 'qemu': 'kvm'}
    protected_pkgs: set[str] = set()
    for gtype in (vm_guest_type, VM_GUEST_ALIASES.get(vm_guest_type, '')):
        protected_pkgs.update(GUEST_PLATFORM_PKGS.get(gtype, []))

    MODULE_PACKAGES = {
        # VirtualBox
        'vboxguest':    'virtualbox-guest-dkms',
        'vboxsf':       'virtualbox-guest-dkms',
        'vboxvideo':    'virtualbox-guest-dkms',
        # VMware
        'vmw_vmci':     'open-vm-tools',
        'vmwgfx':       'open-vm-tools',
        'vsock':        'open-vm-tools',
        'vmw_balloon':  'open-vm-tools',
        'vmxnet3':      'open-vm-tools',
        'pvscsi':       'open-vm-tools',
        # NVIDIA
        'nvidia':           'nvidia-kernel-dkms',
        'nvidia_drm':       'nvidia-kernel-dkms',
        'nvidia_modeset':   'nvidia-kernel-dkms',
        'nvidia_uvm':       'nvidia-kernel-dkms',
        # Broadcom
        'wl':           'broadcom-sta-dkms',
        # Hyper-V
        'hv_vmbus':     'hyperv-daemons',
        'hv_storvsc':   'hyperv-daemons',
        'hv_netvsc':    'hyperv-daemons',
        'hv_utils':     'hyperv-daemons',
        'hv_balloon':   'hyperv-daemons',
    }

    # Systemd services installed by each package
    PKG_SERVICES = {
        'virtualbox-guest-utils': [
            'vboxadd.service', 'vboxadd-service.service',
            'vbox-guest-utils.service',
        ],
        'virtualbox-guest-dkms': [
            'vboxadd.service',
        ],
        'open-vm-tools': [
            'open-vm-tools.service', 'vmtoolsd.service',
            'open-vm-tools-desktop.service',
        ],
        'open-vm-tools-desktop': [
            'vmware-vmblock-fuse.service',
        ],
        'nvidia-persistenced': [
            'nvidia-persistenced.service',
        ],
        'nvidia-kernel-dkms': [
            'nvidia-hibernate.service', 'nvidia-resume.service',
            'nvidia-suspend.service',
        ],
        'hyperv-daemons': [
            'hv-fcopy-daemon.service', 'hv-kvp-daemon.service',
            'hv-vss-daemon.service',
        ],
    }

    # X11 session scripts, XDG autostart and modprobe.d files left by each package
    PKG_AUTOSTART = {
        'virtualbox-guest-x11': [
            '/etc/X11/Xsession.d/98vboxadd-xclient',
            '/etc/xdg/autostart/vboxclient.desktop',
        ],
        'virtualbox-guest-utils': [
            '/etc/X11/Xsession.d/98vboxadd-xclient',
        ],
        'open-vm-tools-desktop': [
            '/etc/xdg/autostart/vmware-user.desktop',
            '/etc/X11/Xsession.d/70vmware-user',
        ],
        'open-vm-tools': [
            '/etc/vmware-tools/scripts/vmware/network',
            '/etc/vmware-tools/scripts/vmware/statechange.subr',
        ],
        'nvidia-kernel-dkms': [
            '/etc/modprobe.d/nvidia-blacklist-nouveau.conf',
            '/etc/modprobe.d/nvidia.conf',
            '/etc/modprobe.d/nvidia-dkms.conf',
        ],
        'nvidia-driver': [
            '/etc/modprobe.d/nvidia-blacklist-nouveau.conf',
            '/etc/modprobe.d/nvidia.conf',
        ],
        'broadcom-sta-dkms': [
            '/etc/modprobe.d/blacklist-bcm43.conf',
            '/etc/modprobe.d/wl.conf',
        ],
        'bcmwl-kernel-source': [
            '/etc/modprobe.d/blacklist-bcm43.conf',
            '/etc/modprobe.d/wl.conf',
        ],
    }

    SYSTEMD_DIRS = [
        '/etc/systemd/system',
        '/lib/systemd/system',
        '/usr/lib/systemd/system',
    ]

    def _is_installed(pkg):
        try:
            r = subprocess.run(
                ['dpkg-query', '-W', '-f=${Status}', pkg],
                capture_output=True, text=True
            )
            return 'install ok installed' in r.stdout
        except Exception:
            return True

    orphans = []
    seen_paths: set[str] = set()

    def _add(entry: dict):
        if entry['path'] not in seen_paths:
            seen_paths.add(entry['path'])
            orphans.append(entry)

    # --- /etc/modules and /etc/modules-load.d/ ---
    def _scan_modload_file(path):
        try:
            with open(path) as f:
                for line in f:
                    mod = line.strip().lstrip('#').strip()
                    if not mod or mod.startswith('#'):
                        continue
                    pkg = MODULE_PACKAGES.get(mod)
                    if pkg and pkg not in protected_pkgs and not _is_installed(pkg):
                        _add({
                            'module': mod, 'source': os.path.basename(path),
                            'path': path, 'type': 'modules-load',
                        })
        except Exception:
            pass

    if os.path.isfile('/etc/modules'):
        _scan_modload_file('/etc/modules')
    if os.path.isdir('/etc/modules-load.d'):
        for fname in os.listdir('/etc/modules-load.d'):
            _scan_modload_file(os.path.join('/etc/modules-load.d', fname))

    # --- /etc/modprobe.d/ ---
    if os.path.isdir('/etc/modprobe.d'):
        for fname in os.listdir('/etc/modprobe.d'):
            fpath = os.path.join('/etc/modprobe.d', fname)
            try:
                with open(fpath) as f:
                    content = f.read()
                for mod, pkg in MODULE_PACKAGES.items():
                    if pkg in protected_pkgs:
                        continue
                    if mod in content and not _is_installed(pkg):
                        _add({
                            'module': mod, 'source': fname,
                            'path': fpath, 'type': 'modprobe',
                        })
                        break
            except Exception:
                pass

    # --- Orphaned systemd service files ---
    for pkg, services in PKG_SERVICES.items():
        if pkg in protected_pkgs or _is_installed(pkg):
            continue
        for svc in services:
            for sdir in SYSTEMD_DIRS:
                svc_path = os.path.join(sdir, svc)
                if os.path.exists(svc_path):
                    _add({
                        'module': svc, 'source': svc,
                        'path': svc_path, 'type': 'systemd',
                    })

    # --- Orphaned X11/XDG autostart files ---
    for pkg, paths in PKG_AUTOSTART.items():
        if pkg in protected_pkgs or _is_installed(pkg):
            continue
        for path in paths:
            if os.path.exists(path):
                _add({
                    'module': os.path.basename(path),
                    'source': os.path.basename(path),
                    'path': path, 'type': 'autostart',
                })

    return orphans


def get_autoremove_packages() -> list[str]:
    """Returns list of packages flagged for autoremoval by apt."""
    packages = []
    try:
        result = subprocess.run(
            ['apt-get', '--dry-run', 'autoremove'],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith('Remv '):
                pkg = line.split()[1]
                packages.append(pkg)
    except Exception as e:
        print(f"[cache] Error getting autoremove list: {e}")
    return packages



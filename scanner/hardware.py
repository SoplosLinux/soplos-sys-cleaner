"""
Hardware detection using four complementary layers:
  0. dracut conf — /etc/dracut.conf.d/*.conf install_items + add_drivers
                   (system's own declaration of what must always be in initramfs)
  1. lspci -nn  — all PCI devices (GPU, audio, network, chipset, USB ctrl, etc.)
  2. lsusb      — all USB devices (BT dongles, WiFi adapters, webcams, HID, etc.)
  3. lsmod + modinfo — firmware files actively loaded by running kernel modules

VM guest detection (layer 4):
  systemd-detect-virt — detects kvm, qemu, vmware, oracle (VirtualBox),
                        microsoft (Hyper-V), xen, parallels, bhyve, none, etc.

The union of all layers determines what firmware and drivers the system
needs.  Anything not matched by any layer is a candidate for removal.
"""

import os
import re
import subprocess

from utils.constants import PROTECTED_FIRMWARE_ALWAYS

# ---------------------------------------------------------------------------
# Vendor ID → firmware directory prefixes
# Each entry covers ALL firmware subdirs that vendor's hardware may need.
# ---------------------------------------------------------------------------
PCI_VENDOR_FIRMWARE: dict[str, list[str]] = {
    # AMD — GPU, APU, audio, chipset, USB
    '1002': ['amdgpu', 'radeon', 'amd'],
    # Intel — GPU, audio, WiFi (some Intel WiFi chips appear as PCI)
    '8086': ['i915', 'intel', 'iwlwifi'],
    # NVIDIA
    '10de': ['nvidia'],
    # Realtek — PCIe WiFi and audio
    '10ec': ['rtlwifi', 'rtw88', 'rtw89', 'rtl_bt', 'rtl8761b', 'rtl8821c',
             'rtl8822c', 'rtl8852a', 'rtl8852b', 'rtl8852c'],
    # Qualcomm / Atheros — PCIe WiFi
    '168c': ['ath10k', 'ath11k', 'ath12k', 'qca'],
    # Broadcom — PCIe WiFi
    '14e4': ['brcm'],
    # MediaTek — PCIe WiFi
    '14c3': ['mediatek'],
    # Marvell — network / WiFi
    '11ab': ['libertas', 'mwl8k', 'mwifiex'],
    '1b4b': ['libertas'],
    # VMware guest
    '15ad': ['vmwgfx'],
    # VirtualBox guest
    '80ee': [],
    # Red Hat / QEMU Virtio (KVM/QEMU guest devices — virtio-pci, virtio-gpu, etc.)
    '1af4': [],
}

USB_VENDOR_FIRMWARE: dict[str, list[str]] = {
    # Intel — USB Bluetooth
    '8087': ['intel', 'iwlwifi'],
    # Realtek — USB WiFi and Bluetooth
    '0bda': ['rtlwifi', 'rtw88', 'rtw89', 'rtl_bt', 'rtl8761b', 'rtl8821c',
              'rtl8822c', 'rtl8852a', 'rtl8852b', 'rtl8852c'],
    # Qualcomm Atheros — USB Bluetooth
    '0cf3': ['qca', 'ath3k'],
    # Broadcom — USB Bluetooth / WiFi
    '0a5c': ['brcm'],
    '0489': ['brcm'],
    # MediaTek — USB WiFi
    '0e8d': ['mediatek'],
    # Ralink (now MediaTek) — USB WiFi
    '148f': ['rt2870', 'rt73usb', 'rt2500usb'],
    # Marvell — USB
    '1286': ['mwifiex'],
    # ath3k generic
    '04ca': ['qca'],
    # Cambridge Silicon Radio (CSR) Bluetooth
    '0a12': [],
}

# ---------------------------------------------------------------------------
# Vendor ID → PCI class → firmware map for GPU/display detection
# Used to identify GPU vendor independently for the Drivers tab label
# ---------------------------------------------------------------------------
GPU_CLASS_PREFIXES = {'0300', '0302', '0380'}  # VGA, 3D, Display

# ---------------------------------------------------------------------------
# Packages associated with each vendor (hardware absent → package removable)
# ---------------------------------------------------------------------------
PCI_VENDOR_PACKAGES: dict[str, list[str]] = {
    '10de': [  # NVIDIA
        'nvidia-driver', 'nvidia-driver-bin', 'nvidia-driver-libs',
        'nvidia-kernel-dkms', 'nvidia-kernel-support',
        'nvidia-alternative', 'nvidia-egl-icd',
        'libglx-nvidia0', 'libgl1-nvidia-glx', 'libnvidia-glcore',
        'libnvidia-encode1', 'libnvidia-cfg1', 'libnvidia-ml1',
        'libnvidia-fbc1', 'nvidia-vdpau-driver',
        'xserver-xorg-video-nvidia', 'nvidia-smi',
        'nvidia-settings', 'nvidia-modprobe', 'nvidia-persistenced',
        'nvidia-vulkan-icd', 'firmware-nvidia-graphics',
    ],
    '1002': [  # AMD
        'xserver-xorg-video-amdgpu',
        'xserver-xorg-video-ati',
        'xserver-xorg-video-radeon',
        'radeontop',
    ],
    '8086': [  # Intel
        'xserver-xorg-video-intel',
        'intel-media-va-driver',
        'intel-gpu-tools',
        'intel-opencl-icd',
    ],
    '15ad': [  # VMware
        'xserver-xorg-video-vmware',
        'open-vm-tools', 'open-vm-tools-desktop',
    ],
    '80ee': [  # VirtualBox
        'virtualbox-guest-x11',
        'virtualbox-guest-utils',
        'virtualbox-guest-dkms',
    ],
}

# KVM is not a PCI vendor ID — detected separately via /dev/kvm + lsmod
KVM_PACKAGES = [
    'qemu-system-x86', 'qemu-system-common', 'qemu-utils',
    'qemu-block-extra', 'libvirt-daemon', 'libvirt-daemon-system',
    'libvirt-clients', 'virt-manager', 'virt-viewer',
    'bridge-utils', 'dnsmasq-base', 'ovmf', 'cpu-checker',
    'libguestfs-tools',
]
KVM_FIRMWARE = ['qemu']


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_hardware() -> dict:
    """
    Scan system hardware via four layers + VM guest detection.

    Returns a dict:
      'dracut_fw_dirs'     : set[str]  — firmware dirs declared in dracut conf (layer 0)
      'pci_vendors'        : list[str] — PCI vendor IDs detected (e.g. ['1002','8086'])
      'usb_vendors'        : list[str] — USB vendor IDs detected
      'gpu_vendors_named'  : list[str] — human names of GPU vendors (for UI label)
      'active_fw_files'    : set[str]  — firmware file paths loaded by lsmod+modinfo
      'kvm_present'        : bool      — True if this machine IS a KVM host
      'vm_guest_type'      : str       — 'none' on bare metal, else 'kvm','vmware','oracle',
                                         'microsoft','xen','qemu','parallels', etc.
    """
    dracut_fw_dirs    = _scan_dracut_conf()
    pci_vendors       = _scan_pci()
    usb_vendors       = _scan_usb()
    gpu_vendors_named = _detect_gpu_names(pci_vendors)
    active_fw_files   = _scan_active_firmware()
    kvm_present       = _detect_kvm()
    vm_guest_type     = _detect_vm_guest()

    return {
        'dracut_fw_dirs': dracut_fw_dirs,
        'pci_vendors': list(pci_vendors),
        'usb_vendors': list(usb_vendors),
        'gpu_vendors_named': gpu_vendors_named,
        'active_fw_files': active_fw_files,
        'kvm_present': kvm_present,
        'vm_guest_type': vm_guest_type,
    }


def get_firmware_protection_set(hardware: dict) -> set[str]:
    """
    Returns a set of firmware directory names (under /lib/firmware) that
    must be protected for this system.

    Layer 0 (highest priority): dracut conf — install_items + add_drivers modules
    Layer 1: PCI vendor map
    Layer 2: USB vendor map
    Layer 3: lsmod + modinfo active firmware files
    Always:  PROTECTED_FIRMWARE_ALWAYS from constants
    """
    protected: set[str] = set(PROTECTED_FIRMWARE_ALWAYS)

    # Layer 0: dracut conf (soplos.conf and any other conf in /etc/dracut.conf.d/)
    protected.update(hardware.get('dracut_fw_dirs', set()))

    # Layer 1: PCI vendors
    for vid in hardware.get('pci_vendors', []):
        protected.update(PCI_VENDOR_FIRMWARE.get(vid, []))

    # KVM
    if hardware.get('kvm_present'):
        protected.update(KVM_FIRMWARE)

    # Layer 2: USB vendors
    for vid in hardware.get('usb_vendors', []):
        protected.update(USB_VENDOR_FIRMWARE.get(vid, []))

    # Layer 3: active firmware files → extract top-level dir under /lib/firmware
    fw_path = '/lib/firmware'
    for fw_file in hardware.get('active_fw_files', set()):
        # fw_file may be 'rtl_bt/rtl8761bu_fw.bin' or 'amdgpu/green_sardine_me.bin'
        # Strip leading slash in case modinfo returns absolute paths
        fw_file = fw_file.lstrip('/')
        parts = fw_file.split('/')
        # Skip 'lib', 'firmware' prefixes from absolute paths
        if parts and parts[0] in ('lib', 'firmware', ''):
            parts = [p for p in parts if p not in ('lib', 'firmware', '')]
        if parts and parts[0]:
            top = parts[0]
            if os.path.isdir(os.path.join(fw_path, top)):
                protected.add(top)

    return protected


def is_firmware_dir_protected(family: str, protection_set: set[str]) -> bool:
    """True if this /lib/firmware subdirectory must not be removed."""
    name_lower = family.lower()
    # Direct match
    if family in protection_set:
        return True
    # Prefix match: e.g. protection_set has 'intel' and family is 'intel-ucode'
    return any(p and (name_lower.startswith(p.lower()) or p.lower() in name_lower)
               for p in protection_set)


def get_all_firmware_families() -> list[str]:
    """Returns sorted list of subdirectory names in /lib/firmware."""
    fw_path = '/lib/firmware'
    families = []
    if os.path.isdir(fw_path):
        for entry in os.scandir(fw_path):
            if entry.is_dir():
                families.append(entry.name)
    return sorted(families)


def get_firmware_sizes(families: list[str]) -> dict[str, int]:
    """Returns {family_name: size_kb} for each firmware directory."""
    sizes = {}
    for name in families:
        path = f'/lib/firmware/{name}'
        try:
            res = subprocess.run(
                ['du', '-sk', path], capture_output=True, text=True, timeout=10
            )
            sizes[name] = int(res.stdout.split()[0]) if res.stdout.strip() else 0
        except Exception:
            sizes[name] = 0
    return sizes


def get_unnecessary_hardware_packages(
    pci_vendors: list[str],
    usb_vendors: list[str],
    kvm_present: bool,
) -> list[dict]:
    """
    Returns packages installed for hardware NOT present in this system.
    Each entry: {'name', 'description', 'installed_size', 'vendor'}
    """
    from scanner.packages import is_package_installed, get_package_description, get_installed_size_kb

    present = set(pci_vendors) | set(usb_vendors)
    results = []

    for vid, packages in PCI_VENDOR_PACKAGES.items():
        if vid in present:
            continue
        for pkg in packages:
            if is_package_installed(pkg):
                results.append({
                    'name': pkg,
                    'description': get_package_description(pkg),
                    'installed_size': get_installed_size_kb(pkg),
                    'vendor': _vendor_label(vid),
                })

    if not kvm_present:
        for pkg in KVM_PACKAGES:
            if is_package_installed(pkg):
                results.append({
                    'name': pkg,
                    'description': get_package_description(pkg),
                    'installed_size': get_installed_size_kb(pkg),
                    'vendor': 'KVM/QEMU',
                })

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan_dracut_conf() -> set[str]:
    """
    Layer 0: read all /etc/dracut.conf.d/*.conf files and extract firmware
    directories that dracut injects into the initramfs.

    Two sources inside conf files:
      install_items += " /lib/firmware/xxx/ ... "
        → extracts directory name 'xxx' directly

      add_drivers += " mod1 mod2 ... "
        → runs modinfo -F firmware on each module to find its firmware dirs
    """
    fw_dirs: set[str] = set()
    conf_dir = '/etc/dracut.conf.d'

    if not os.path.isdir(conf_dir):
        return fw_dirs

    # Collect all conf files
    conf_files = []
    try:
        for entry in os.scandir(conf_dir):
            if entry.is_file() and entry.name.endswith('.conf'):
                conf_files.append(entry.path)
    except Exception:
        return fw_dirs

    install_items_re = re.compile(r'install_items\+?=\s*["\']([^"\']+)["\']')
    add_drivers_re   = re.compile(r'add_drivers\+?=\s*["\']([^"\']+)["\']')

    extra_modules: list[str] = []

    for conf_path in conf_files:
        try:
            with open(conf_path, 'r', errors='replace') as f:
                content = f.read()
        except Exception:
            continue

        # Extract install_items — paths like /lib/firmware/rtlwifi/
        for match in install_items_re.finditer(content):
            for token in match.group(1).split():
                token = token.strip().rstrip('/')
                # Match /lib/firmware/<dirname>
                m = re.match(r'^/lib/firmware/([^/]+)$', token)
                if m:
                    fw_dirs.add(m.group(1))

        # Extract add_drivers — module names
        for match in add_drivers_re.finditer(content):
            for mod in match.group(1).split():
                mod = mod.strip()
                if mod:
                    extra_modules.append(mod)

    # Resolve firmware dirs for dracut-declared modules via modinfo
    for mod in extra_modules:
        try:
            info = subprocess.check_output(
                ['modinfo', '-F', 'firmware', mod],
                text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            for fw_file in info.splitlines():
                fw_file = fw_file.strip().lstrip('/')
                parts = [p for p in fw_file.split('/') if p and p not in ('lib', 'firmware')]
                if parts and parts[0]:
                    fw_dirs.add(parts[0])
        except Exception:
            pass

    return fw_dirs


def _scan_pci() -> set[str]:
    """Extract all PCI vendor IDs via lspci -nn."""
    vendors: set[str] = set()
    try:
        output = subprocess.check_output(['lspci', '-nn'], text=True, timeout=10)
        for line in output.splitlines():
            match = re.search(r'\[([0-9a-fA-F]{4}):[0-9a-fA-F]{4}\]', line)
            if match:
                vendors.add(match.group(1).lower())
    except Exception as e:
        print(f'[hardware] lspci error: {e}')
    return vendors


def _scan_usb() -> set[str]:
    """Extract all USB vendor IDs via lsusb."""
    vendors: set[str] = set()
    try:
        output = subprocess.check_output(['lsusb'], text=True, timeout=10)
        for line in output.splitlines():
            # Format: Bus NNN Device NNN: ID VVVV:PPPP Description
            match = re.search(r'ID\s+([0-9a-fA-F]{4}):[0-9a-fA-F]{4}', line)
            if match:
                vendors.add(match.group(1).lower())
    except Exception as e:
        print(f'[hardware] lsusb error: {e}')
    return vendors


def _detect_gpu_names(pci_vendors: set[str]) -> list[str]:
    """Maps detected PCI vendor IDs to human-readable GPU/hardware vendor names."""
    GPU_VENDOR_NAMES = {
        '10de': 'NVIDIA',
        '1002': 'AMD',
        '8086': 'Intel',
        '15ad': 'VMware',
        '80ee': 'VirtualBox',
        '1af4': 'QEMU/KVM',
    }
    names = []
    for vid in pci_vendors:
        if vid in GPU_VENDOR_NAMES:
            name = GPU_VENDOR_NAMES[vid]
            if name not in names:
                names.append(name)
    return names


def _find_modinfo() -> str | None:
    """Return the full path to modinfo, or None if not found."""
    for path in ('modinfo', '/sbin/modinfo', '/usr/sbin/modinfo', '/usr/bin/modinfo'):
        try:
            subprocess.run([path, '--version'], capture_output=True, timeout=3)
            return path
        except (FileNotFoundError, Exception):
            continue
    return None


def _scan_active_firmware() -> set[str]:
    """
    Layer 3: query modinfo for every loaded module to get firmware files
    that the running kernel is actually using.

    Layer 3b: parse dmesg for 'Direct firmware load for <path>' messages —
    catches drivers that load firmware dynamically without declaring it in
    module metadata (e.g. r8169/r8125 → rtl_nic/, btrtl → rtl_bt/).

    Returns a set of firmware file paths (relative to /lib/firmware).
    """
    fw_files: set[str] = set()

    # Layer 3: modinfo per loaded module
    modinfo_bin = _find_modinfo()
    if modinfo_bin:
        try:
            lsmod_out = subprocess.check_output(['lsmod'], text=True, timeout=10)
            modules = []
            for line in lsmod_out.splitlines()[1:]:
                parts = line.split()
                if parts:
                    modules.append(parts[0])

            for mod in modules:
                try:
                    info = subprocess.check_output(
                        [modinfo_bin, '-F', 'firmware', mod],
                        text=True, timeout=5, stderr=subprocess.DEVNULL
                    )
                    for fw in info.splitlines():
                        fw = fw.strip()
                        if fw:
                            fw_files.add(fw)
                except Exception:
                    pass
        except Exception as e:
            print(f'[hardware] lsmod/modinfo error: {e}')

    # Layer 3b: kernel log — firmware actually requested at boot
    # journalctl -k persists across reboots; dmesg is a fallback for systems without systemd
    fw_re = re.compile(
        r'(?:Direct firmware load for|firmware:|loaded firmware(?: image)?)'
        r'\s+(?:/lib/firmware/)?([^\s:,]+\.(?:bin|fw|ucode|cis|dsp|elf|nvm|txt))',
        re.IGNORECASE
    )

    def _parse_fw_lines(text: str):
        for line in text.splitlines():
            m = fw_re.search(line)
            if m:
                fw_files.add(m.group(1).strip())

    journal_ok = False
    try:
        journal_out = subprocess.check_output(
            ['journalctl', '-k', '--no-pager', '-o', 'short-monotonic'],
            text=True, timeout=15, stderr=subprocess.DEVNULL
        )
        _parse_fw_lines(journal_out)
        journal_ok = True
    except Exception:
        pass

    if not journal_ok:
        try:
            dmesg_out = subprocess.check_output(
                ['dmesg'], text=True, timeout=10, stderr=subprocess.DEVNULL
            )
            _parse_fw_lines(dmesg_out)
        except Exception as e:
            print(f'[hardware] kernel log error: {e}')

    return fw_files


def _detect_kvm() -> bool:
    """True if KVM/QEMU virtualisation is active on this host (KVM host, not guest)."""
    if os.path.exists('/dev/kvm'):
        return True
    try:
        output = subprocess.check_output(['lsmod'], text=True, timeout=5)
        for mod in ('kvm_intel', 'kvm_amd', 'kvm'):
            if mod in output:
                return True
    except Exception:
        pass
    return False


def _detect_vm_guest() -> str:
    """
    Detect if this system is running as a guest inside a hypervisor.

    Uses systemd-detect-virt as primary method, with fallbacks via
    /sys/hypervisor/type and DMI strings.

    Returns the hypervisor name string:
      'none'       — bare metal
      'kvm'        — KVM/QEMU guest
      'qemu'       — QEMU without KVM
      'vmware'     — VMware (ESXi, Workstation, Fusion)
      'oracle'     — VirtualBox (Oracle VM)
      'microsoft'  — Hyper-V
      'xen'        — Xen
      'parallels'  — Parallels Desktop
      'bhyve'      — bhyve
      'docker'     — Docker container
      'lxc'        — LXC container
      etc.
    """
    # Primary: systemd-detect-virt (most reliable, covers all major hypervisors)
    try:
        result = subprocess.run(
            ['systemd-detect-virt'],
            capture_output=True, text=True, timeout=5
        )
        virt = result.stdout.strip().lower()
        if virt:
            return virt
    except Exception:
        pass

    # Fallback 1: /sys/hypervisor/type (Xen exposes this)
    try:
        with open('/sys/hypervisor/type') as f:
            htype = f.read().strip().lower()
            if htype:
                return htype
    except Exception:
        pass

    # Fallback 2: DMI product name via /sys/class/dmi/id/
    try:
        for dmi_file in ('/sys/class/dmi/id/product_name', '/sys/class/dmi/id/sys_vendor'):
            try:
                with open(dmi_file) as f:
                    val = f.read().strip().lower()
                    if 'vmware' in val:
                        return 'vmware'
                    if 'virtualbox' in val:
                        return 'oracle'
                    if 'qemu' in val or 'kvm' in val:
                        return 'kvm'
                    if 'microsoft' in val or 'hyper-v' in val:
                        return 'microsoft'
                    if 'xen' in val:
                        return 'xen'
                    if 'parallels' in val:
                        return 'parallels'
            except Exception:
                pass
    except Exception:
        pass

    return 'none'


def _vendor_label(vid: str) -> str:
    labels = {
        '10de': 'NVIDIA', '1002': 'AMD', '8086': 'Intel',
        '15ad': 'VMware', '80ee': 'VirtualBox',
    }
    return labels.get(vid, vid.upper())

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/en/).

## [1.0.2-9] - 2026-06-29

### 🐛 Fixed
- **DKMS orphan false positives (Soplos kernel)**: Fixed indentation logic bug in `get_orphan_dkms_modules` and added specific protections for Soplos kernels (like `bore-ntsync`). If a package like `v4l2loopback-dkms` or `nvidia-driver` is installed, its compiled modules will no longer be marked for deletion even if the version string is injected with `kernel-` prefix.

---

## [1.0.2-8] - 2026-06-29

### 🐛 Fixed
- **Kernel false-positive active detection (`kernels.py`)**: `version in current` used substring matching — `6.1.0-2-amd64` was a substring of `6.1.0-27-amd64`, so an old kernel could be marked as active and protected from removal. Changed to exact equality (`==`) in both `get_installed_kernels` and `_find_unmatched_modules_dirs`.
- **`_clean_file` mishandled commented module entries (`root_helper.py`)**: `l.strip().lstrip('#')` left a leading space on `# vboxguest` → `' vboxguest'` which didn't match the module name, so orphaned comment lines were never removed. Conversely, `#vboxguest` (no space) matched and was deleted. Fixed with `.strip().lstrip('#').strip()`.
- **Race condition in APT Cache orphan cleanup (`cache_tab.py`)**: `clean_module_refs` (which runs `dracut -f`) and `apt_autoremove` were dispatched to the root_helper concurrently — two threads writing/reading the same stdin/stdout pipe could corrupt the JSON protocol. `apt_autoremove` is now chained in the callback of `clean_module_refs`.
- **"Detected hardware" label included non-GPU PCI vendors (`hardware.py`)**: `_detect_gpu_names()` received all PCI vendor IDs; on a KVM host, virtio devices (vendor `1af4`) were present in lspci and the label incorrectly showed "QEMU/KVM". Fixed by passing `gpu_pci_vendors` (class 03xx devices only).
- **VM guest type missing from "Detected hardware" label (`main_window.py`)**: `hardware_summary` only listed GPU vendor names and KVM host status. Running inside VirtualBox, VMware, Hyper-V etc. was never shown. Added human-readable guest VM labels for all supported hypervisors.
- **Locale sizes reported as 0 KB when `du` has partial read errors (`locales.py`)**: `check=True` caused `CalledProcessError` when `du` returned exit code 1 (common in `/usr/share/locale` due to restricted subdirs), discarding the partial stdout result. Removed `check=True`; stdout is now used regardless of return code.
- **DKMS orphan scanner only checked the running kernel (`hardware.py`)**: `/var/lib/dkms/<mod>/<ver>/<kver>/` was only scanned for the currently booted kernel. Compiled modules for other installed kernels (not currently active) were never detected. Scanner now iterates all kernel-version subdirs (matched by `^\d+\.\d+`) under each DKMS version directory.
- **`apt_purge` triggered after failed DKMS cleanup (`drivers_tab.py`)**: `on_dkms_done` did not check the result of the DKMS removal step — even if `dracut -f` failed, `apt_purge` was dispatched next with `rebuild_initrd: False`, leaving the system with purged packages but an outdated initrd. Now aborts on DKMS step failure. Also corrected: when DKMS step succeeds and APT packages follow, `rebuild_initrd` is now `True` so dracut runs after the purge.
- **Substring match for module names in modprobe.d files (`cache.py`)**: `if mod in content` was a plain substring search — module `'wl'` matched inside `'brcmwl'`, potentially flagging valid config files as orphaned and deleting them. Replaced with `re.search(r'\b<mod>\b', content)` for word-boundary matching.
- **Service/autostart files flagged as orphans when a co-owning package is still installed (`cache.py`)**: `vboxadd.service` is listed under both `virtualbox-guest-utils` and `virtualbox-guest-dkms`. When only `virtualbox-guest-utils` was autoremoved, the service was shown as orphaned even though `virtualbox-guest-dkms` (still installed) legitimately owns it. The user cleaned the file but DKMS kept compiling `vboxguest`. Added reverse-map check: a file is only flagged as orphaned when ALL packages that list it are uninstalled.
- **`root_scan.py` referenced non-existent fields (`root_scan.py`)**: This script was superseded by `root_helper.py` but still referenced `k.packages` (removed from `KernelInfo`) and lacked calls to `get_orphan_module_refs`, `get_firmware_sizes` and other newer scanners. Marked as deprecated — `root_helper.py` is the active entry point.
- **CPU temperature always showed 20°C on some boards (`overview_tab.py`)**: The overview panel read `/sys/class/thermal/thermal_zone0/temp` directly, which on many AMD/Ryzen boards (and the Zyren) maps to `acpitz` — a stub driver that always returns 20°C. Replaced with a prioritized hwmon reader: searches `/sys/class/hwmon/*/name` for `k10temp` (AMD Tctl) first, then `coretemp` (Intel Package/Core 0), then other common drivers, and only falls back to `acpitz`/`thermal_zone` as a last resort. Within each hwmon, labeled inputs (Tctl, Package, Core 0) are preferred over lowest-indexed.

---

## [1.0.2-7] - 2026-06-24

### 🐛 Fixed
- **VirtualBox (and other hypervisor) guest service files shown as orphans when running inside VM**: `get_orphan_module_refs()` was unaware of the current hypervisor guest type. When Boro/Tyron runs inside VirtualBox with Guest Additions installed from the ISO (not via apt), files like `vboxadd.service`, `98vboxadd-xclient` and `vboxclient.desktop` existed on disk without a matching dpkg package, so they were incorrectly reported as orphaned. The function now accepts `vm_guest_type` (from `systemd-detect-virt`) and protects all files belonging to the current guest platform: VirtualBox (`oracle`), VMware (`vmware`), Hyper-V (`microsoft`), KVM/QEMU (`kvm`/`qemu`).
- **Duplicate entries for `98vboxadd-xclient`**: The file `/etc/X11/Xsession.d/98vboxadd-xclient` was listed in both `virtualbox-guest-x11` and `virtualbox-guest-utils` entries of `PKG_AUTOSTART`, causing it to appear twice in the orphans list. Added `seen_paths` deduplication so each file path is reported at most once.

---

## [1.0.2-6] - 2026-06-14

### 🐛 Fixed
- **SPICE guest tools shown as removable in KVM/QEMU VMs (virt-manager)**: `VM_GUEST_PACKAGES` has separate entries for `kvm` and `qemu`, both containing `spice-vdagent` and `spice-webdavd`. When `systemd-detect-virt` returns `kvm`, only the `kvm` entry was protected — the `qemu` entry caused the same packages to appear as removable. Added alias logic so that detecting `kvm` also protects `qemu` packages and vice versa.

---

## [1.0.2-5] - 2026-06-12

### 🐛 Fixed
- **Firmware removal was not permanent — files restored on every `apt upgrade`**: `do_remove_firmware` was deleting files from `/lib/firmware/` directly without touching the APT packages that own them (`firmware-realtek`, `firmware-amd-graphics`, `firmware-iwlwifi`, etc.). Any subsequent `apt full-upgrade` restored the deleted files because the packages were still registered as installed. The action now runs `apt purge` for the owning package when all its firmware directories are being removed, covering: `firmware-amd-graphics` (amdgpu, radeon), `firmware-intel-graphics` (i915), `firmware-intel-sound` (intel), `firmware-iwlwifi` (iwlwifi), `firmware-realtek` (rtlwifi, rtw88, rtw89, rtl_bt, rtl8761b–rtl8852c, rtl_nic), `firmware-brcm80211` (brcm), `firmware-atheros` (ath10k, ath11k, ath12k, qca), `firmware-mediatek` (mediatek, mt76), `firmware-libertas` (libertas, mwl8k, mwifiex), `firmware-nvidia-graphics` (nvidia). Generic bundles (`firmware-linux-nonfree`, `firmware-misc-nonfree`) are not purged as they contain firmware for many unrelated hardware families; their directories are deleted directly as before.

---

## [1.0.2-4] - 2026-06-09

### 🐛 Fixed
- **DKMS orphan detector — active driver shown as orphan (NVIDIA false positive)**: The DKMS directory for NVIDIA is named `nvidia`, but the code tried package names `nvidia-dkms`, `nvidia` and `linux-nvidia`. None of those exist — the real package is `nvidia-kernel-dkms`. Added `DKMS_MODULE_PACKAGES` mapping covering NVIDIA, VirtualBox guest (`vboxguest` → `virtualbox-guest-dkms`), Broadcom (`broadcom-sta`, `wl` → `broadcom-sta-dkms` / `bcmwl-kernel-source`), ZFS, v4l2loopback, bbswitch and other known mismatches between DKMS directory name and package name.
- **DKMS orphan detector — old compiled versions not detected after upgrade**: When a driver is upgraded (e.g. NVIDIA 580.126.20 → 580.159.04), the old compiled modules in `/var/lib/dkms/nvidia/580.126.20/<kver>/` were not flagged as orphans because the new `nvidia-kernel-dkms` package was found installed. The detector now first checks for the DKMS source directory `/usr/src/<module>-<version>/` — its absence is the definitive sign that this specific version has no owning package. A version-string comparison against the installed package version is used as fallback for packages that place sources elsewhere.

---

## [1.0.2-3] - 2026-06-04

### ✨ Added
- **Orphaned DKMS modules — Drivers tab**: New `get_orphan_dkms_modules()` scanner checks `/var/lib/dkms/<module>/<version>/<kernel>/` for compiled `.ko` files whose source package (`*-dkms`) is no longer installed. Shown as `[DKMS]` entries in the Drivers tab alongside regular driver packages. Removed via `dkms remove` or direct directory deletion + `depmod -a` + `dracut -f`.
- **Orphaned module references — APT Cache orphans section**: New `get_orphan_module_refs()` scanner detects leftover references to modules from uninstalled packages across five locations:
  - `/etc/modules` — direct module load entries
  - `/etc/modules-load.d/` — per-file module load configs
  - `/etc/modprobe.d/` — modprobe configuration files
  - systemd unit files (`/etc/systemd/system`, `/lib/systemd/system`, `/usr/lib/systemd/system`) — orphaned service units from VirtualBox, VMware, Hyper-V packages
  - X11/XDG autostart files (`/etc/X11/Xsession.d/`, `/etc/xdg/autostart/`) — orphaned session scripts from `virtualbox-guest-x11`, `open-vm-tools-desktop`
- **Automatic reference cleanup on driver removal**: `do_apt_purge` now calls `_cleanup_module_references()` after purging driver packages, removing entries from `/etc/modules` and `/etc/modules-load.d/` before `dracut -f`. Covers VirtualBox (`vboxguest`, `vboxsf`, `vboxvideo`), VMware (`vmw_vmci`, `vmwgfx`, `vsock`, `vmw_balloon`, `vmxnet3`, `pvscsi`), NVIDIA (`nvidia`, `nvidia_drm`, `nvidia_modeset`, `nvidia_uvm`), Broadcom (`wl`), Hyper-V (`hv_vmbus`, `hv_storvsc`, `hv_netvsc`, `hv_utils`, `hv_balloon`).
- **`clean_module_refs` root action**: New action handles complete cleanup of detected orphaned references — removes module load entries, orphaned modprobe.d files, disables and removes orphaned systemd services (`systemctl disable --now` + file removal + `daemon-reload`), removes orphaned X11/XDG autostart files, then rebuilds initramfs with `dracut -f`.
- **`remove_dkms_orphans` root action**: New action removes selected DKMS orphan module trees via `dkms remove MODULE/VERSION --all`, with fallback to direct `shutil.rmtree`, followed by `depmod -a` + `dracut -f`.

### 🐛 Fixed
- **`VBoxClient: the VirtualBox kernel service is not running` notifications**: After removing `virtualbox-guest-x11` via the Drivers tab, `/etc/X11/Xsession.d/98vboxadd-xclient` and `/etc/xdg/autostart/vboxclient.desktop` were left on disk. At every login, `VBoxClient` was launched by these autostart files, failed to find the kernel module, and generated the error notification. The orphaned autostart scanner now detects these files and `clean_module_refs` removes them.
- **Boot error notifications after any driver removal**: Full coverage — VMware (`/etc/X11/Xsession.d/70vmware-user`, `vmware-user.desktop`, `vmtoolsd.service`, `vmware-vmblock-fuse.service`, `open-vm-tools.service`), NVIDIA (`nvidia-persistenced.service`, `nvidia-hibernate/resume/suspend.service`, `/etc/modprobe.d/nvidia-blacklist-nouveau.conf`, `nvidia.conf`), Broadcom (`/etc/modprobe.d/blacklist-bcm43.conf`, `wl.conf`), Hyper-V (`hv-fcopy/kvp/vss-daemon.service`).
- **Users who removed drivers before this fix**: The orphaned reference scanner runs on every root scan — leftover files from previous removals are shown in APT Cache → Paquetes huérfanos and can be cleaned from there without reinstalling anything.

---

## [1.0.2-2] - 2026-05-29

### ✨ Added
- **Drivers tab — VM guest tools**: New `VM_GUEST_PACKAGES` dict maps `systemd-detect-virt` output to guest tool packages. Tools for the current hypervisor are protected; all others are shown as removable. Covers VirtualBox (`virtualbox-guest-x11/utils/dkms`), VMware (`xserver-xorg-video-vmware`, `open-vm-tools`, `open-vm-tools-desktop`), KVM/QEMU (`spice-vdagent`, `spice-webdavd`), Hyper-V (`hyperv-daemons`), Xen (`xen-utils-guest`, `xe-guest-utilities`).
- **Drivers tab — printer drivers**: USB vendor detection for HP (`hplip`, `hplip-data`), Epson (`epson-inkjet-printer-escpr/2`), Canon (`cnijfilter2`, `scangearmp2`), Brother (`printer-driver-brlaser`), Samsung (`printer-driver-splix`), Kyocera (`printer-driver-c2esp`). Packages only shown as removable when the corresponding USB vendor is not detected.
- **Drivers tab — Wacom tablets**: `xserver-xorg-input-wacom`, `libwacom2` shown as removable when USB vendor `056a` (Wacom) is absent.
- **Drivers tab — Broadcom proprietary WiFi**: `broadcom-sta-dkms`, `bcmwl-kernel-source` shown as removable when PCI vendor `14e4` (Broadcom) is absent.

### 🐛 Fixed
- **Drivers tab — Intel GPU false positive in VMs**: VMs expose Intel chipset devices (i440FX, ICH9) with vendor `8086` in `lspci`, causing Intel GPU driver packages to be incorrectly protected. A new `_scan_gpu_pci_vendors()` function uses `lspci -n` to check PCI class `03xx` and only protects Intel GPU packages when a real Intel GPU is present.
- **Drivers tab — VMware tools shown as removable when running in VMware**: When VirtualBox is configured with VMSVGA display, the VMware PCI vendor `15ad` appears in `lspci`, incorrectly protecting `open-vm-tools`. VM tools are now managed exclusively via `systemd-detect-virt`, not PCI vendor detection.
- **Drivers tab — fixes not applying in production**: All hardware detection improvements were applied to `root_scan.py` but the live app uses `root_helper.py` via pkexec. `root_helper.py` was not updated with `gpu_pci_vendors` and `vm_guest_type` parameters — this is now corrected.
- **Firmwares tab — dracut protection layer missing client-side**: `root_helper.py` was not exporting `dracut_fw_dirs` in the scan JSON. The client-side firmware protection set rebuild now correctly includes firmware directories declared in `/etc/dracut.conf.d/`.
- **Progress bar — showing 100% during operations**: `set_ui_state(..., pulse=True)` now resets `fraction` to `0.0` before calling `pulse()`. Previously the leftover `1.0` fraction from a completed scan persisted as "100%" text during all subsequent indeterminate operations.
- **"Select all" checkbox not resetting after cleanup**: The checkbox remained checked after a successful cleanup and re-scan. Added reset via `handler_block_by_func` + `set_active(False)` in the `on_done` callback of `drivers_tab`, `firmware_tab`, `temp_tab`, `logs_tab`, `user_cache_tab`, and `flatpak_tab`.

---

## [1.0.2-1] - 2026-04-17

### ✨ Added
- **Snap tab redesigned**: Now has two sections like Flatpak — installed snaps with full uninstall (`snap remove --purge`, removes snap and all its data) and old/disabled revisions.
- **VM guest detection**: `systemd-detect-virt` now identifies the hypervisor type (KVM, QEMU, VMware, VirtualBox, Hyper-V, Xen, Parallels…) and displays it in the Drivers tab label. Fallbacks via `/sys/hypervisor/type` and DMI strings.
- **QEMU/KVM guest support**: Added Red Hat/Virtio PCI vendor `1af4` to the hardware map so QEMU guest devices are properly recognised.

### 🐛 Fixed
- **Kernel removal**: After purging kernel packages, `dracut -f` and `update-grub` are now always executed to regenerate the initramfs and update the bootloader. Previously neither was called.
- **`apt-get` → `apt`**: All package management commands in the root helper now use the modern `apt` frontend.
- **Translation coverage**: 27 previously untranslated strings (Drivers tab, Firmware tab, Kernels orphan section, Locales tab) added to all 8 language dictionaries and `.mo` files recompiled.

---

## [1.0.2] - 2026-03-29

### ✨ Added
- **Installed Apps tab**: New user-mode tab listing all manually installed packages with search, size info and selective uninstall via pkexec.
- **Snap tab**: New user-mode tab detecting and removing old/disabled Snap revisions (consistent with Flatpak tab).
- **Firmware sizes**: Each firmware family in the Firmwares tab now shows its disk usage.
- **APT Cache — individual .deb selection**: The APT Cache tab now lists every cached `.deb` file individually, allowing selective deletion instead of all-or-nothing.
- **Auto-scan on open**: User-mode scan now starts automatically on launch without requiring a manual button press.
- **Overview Snap card**: Old Snap revisions now appear as a card in the user-mode overview.
- **Overview Apps card**: Manually installed packages appear as a card in the user-mode overview.
- **"Select all docs" button**: New button in the Languages tab to select all documentation entries at once.

### 🐛 Fixed
- **AMD/GPU firmware protection**: Firmware directories belonging to the detected GPU (amdgpu, radeon, i915…) are now locked in the Firmwares tab, preventing accidental removal.
- **KVM/QEMU/VirtualBox detection**: Virtual machine packages and firmwares are now detected and protected when the corresponding technology is active.
- **Overview grid symmetry**: Cards in the overview now use column-homogeneous layout so incomplete rows still render all cards at equal width.
- **Flatpak tab redesigned**: Now shows two sections — installed Flatpak apps (human-readable name, app ID, version, disk size) and unused runtimes. Previously the tab only showed runtime refs with no useful app information.
- **Flatpak sizes**: Fixed 0 B size display by reading actual disk usage via `du` on the flatpak installation directories. The previous `flatpak list --columns=size` returns download size, always 0 for already-installed items.
- **Flatpak unused runtime detection**: Replaced the naive runtime comparison (which incorrectly flagged the SDK and Platform GL extensions as unused) with delegation to `flatpak uninstall --unused`, which correctly handles extensions, SDK dependencies and transitive references.
- **Apps tab — firmware and kernel filtering**: Firmware and kernel packages no longer appear in the Installed Apps tab after a root-mode cleanup. Packages are now filtered by dpkg section (`kernel`, `firmware`) and by name prefix (`firmware-`, `linux-image-`, `linux-headers-`, etc.).
- **Progress bar stuck at 100%**: Fixed. User-mode scan now uses real progress fractions per step (0 → 0.15 → 0.35 → … → 1.0). Root-mode scan uses a continuous 120 ms pulse timer that stops when the scan completes.

### 🔧 Improved
- **Tab order (user mode)**: Overview → Apps → Flatpak → Snap → User Cache → Trash.
- **Overview card order**: Mirrors tab order in both user and root modes.

---

## [1.0.1] - 2026-03-25

### ✨ Added
- **Dual-Layer Scanning**: Separates User and Administrator scans. Starts with a fast user-level scan, only requesting administrative privileges when explicitly requested via the top header button.
- **Flatpak Cleaning**: New dedicated tab to detect and safely uninstall unused Flatpak runtimes (`flatpak uninstall --unused`).
- **User Cache Cleaning**: New scanner specifically targeting `~/.cache`, grouped by application folders.
- **Trash Management**: New dedicated tab to easily empty the user's local trash (`~/.local/share/Trash`).
- **Dynamic Tabs**: System-critical tabs (GPU Drivers, Firmwares, Kernels, APT, Logs, Languages) now logically remain hidden until an administrative scan is authorized.
- **Unified Overview**: The overview tab now perfectly aggregates sizes and elements from both the user-level and root-level scans dynamically.

### 🐛 Fixed
- **Root Session Refreshing**: Resolved a major architectural frustration where the administrative session was hard-killed (triggering repeated `pkexec` password prompts) just to refresh the UI after a cleanup. The persistent IPC helper is now gracefully reused for subsequent rescans.
- **Silent User Cleanup**: Removed intrusive `pkexec` fallbacks from user-level tasks. Clearing user cache or trash now silently skips unprivileged files instead of throwing root password prompts.
- **Kernel Tab Display**: Fixed a `TypeError` in IPC data deserialization that caused the Kernels tab to crash silently and display completely empty.
- **Root Launch Optimization**: The administrative scan now correctly detects if the application is already running under `sudo` / `root`, bypassing redundant Polkit authentication prompts.

---

## [1.0.0-2] - 2026-03-20

### 🐛 Fixed
- About dialog credits panel on KDE: the credits area now displays with an opaque dark background and square corners instead of transparent or rounded-corner artifacts.
- About dialog app icon standardized to 48×48 pixels.

---

## [1.0.0-1] - 2026-03-20

### ✨ Added
- **Ctrl+Tab / Ctrl+Shift+Tab**: Keyboard shortcuts to cycle forward/backward between tabs.
- **F1 — About dialog**: Press F1 to open the About dialog with version, author, license and website.

### 🐛 Fixed (1.0.0-1)
- **GNOME HeaderBar**: Now displays with correct dark background matching other Soplos apps.
- **GNOME CSD controls**: Minimize/maximize/close buttons no longer affected by the global `button {}` CSS rule.

### 🎉 Features & Improvements
- **Languages & Docs**: New intelligent cleanup tab that protects active system locales and clears translations/help files.
- **Standardized UI**: Implemented Soplos v2.0 Standard with slim tabs and professional HeaderBar (matching WebApp Manager).
- **Core Security**: Consolidated administrative tasks into a single `pkexec` prompt.
- **Advanced Cleaning**: Recursive `__pycache__` cleaning and system cache optimization.
- **Intelligent Protection**: Locked network firmwares and active kernels to prevent system failures.
- **Precision Scanning**: Universal scanner using `du -sk` for accurate and fast size calculation.
- **Hardware Monitoring**: Extended overview including Temperature, GPU, and Disk usage.
- **Global Reach**: Fully localized UI in 8 languages (ES, EN, FR, DE, PT, IT, RO, RU).
- **Responsive Design**: Optimized layout for GTK environments (X11/Wayland/GNOME/KDE/XFCE).
- **Keyboard Shortcuts**: Added Ctrl+W (close), Ctrl+R (rescan), Ctrl+1–7 (tab navigation).
- **Scan Icon**: Enlarged to 128px in Overview tab for better visibility.

### 🐛 Fixed
- Action buttons (Remove, Clean, Autoremove) now re-enable after failed or cancelled operations instead of remaining permanently disabled.
- Progress bar in Kernels tab now closes after cleanup completes.
- Translatable strings in GPU Drivers and Firmware tabs were hardcoded in Spanish; corrected to English as required by the i18n system.
- **Temp Files**: Socket files, named pipes and symlinks (D-Bus, MCP, systemd) are now excluded from the scanner — they are active session files and must not be deleted.
- **Temp Files**: Deletion of root-owned files now uses a single `pkexec` fallback call instead of silently failing with `PermissionError`.
- **APT Cache**: Scanner was only counting `.deb` files, always showing 0 on clean systems. It now also measures the package lists (`/var/lib/apt/lists/`) populated by `apt update`.
- **APT Cache**: "Remove orphaned packages" button is now hidden instead of visually active when there are no orphans — the XFCE theme did not grey out `destructive-action` buttons correctly.
- **Overview**: System usage metrics timer moved to a background thread to prevent UI freezes after scan.
- **Languages tab**: Widget creation deferred until the tab is first opened (lazy loading). Previously, 500–1000+ GTK widgets were created synchronously on scan completion, causing the entire application to freeze on any subsequent interaction.

### 🔧 Improved
- Shared utility function `fmt_size()` consolidated in `utils/constants.py`, eliminating duplication across 6 tab files.
- Duplicate constant definitions (`SUPPORTED_LANGUAGES`, `PROTECTED_FIRMWARE`) removed; single source of truth in their respective modules.
- Unused functions removed: `get_autoremove_size_kb()`, `_get_size()`, `get_total_temp_size()`.
- Misplaced and unused imports cleaned up across all UI and scanner modules.
- Logging in `application.py` unified through the `logger` module (replaced `print()` calls).
- Overview card strings (`items`, `family(s)`, `removable`) are now translatable across all 8 languages.

---

## Types of Changes

- **Added** for new features
- **Improved** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for removed features
- **Fixed** for bug fixes
- **Security** for vulnerabilities

## Author

Developed and maintained by Sergi Perich  
Website: https://soplos.org  
Contact: info@soploslinux.com

## Contributing

To report bugs or request features:
- **Issues**: https://github.com/SoplosLinux/soplos-sys-cleaner/issues
- **Email**: info@soploslinux.com

## Support

- **Documentation**: https://soplos.org
- **Community**: https://soplos.org/forums/
- **Support**: info@soploslinux.com

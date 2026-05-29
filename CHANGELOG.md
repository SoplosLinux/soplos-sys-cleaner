# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/en/).

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

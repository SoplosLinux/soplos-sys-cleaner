# Soplos Sys Cleaner

[![License: GPL-3.0+](https://img.shields.io/badge/License-GPL--3.0%2B-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-1.0.2--5-green.svg)]()

A system cleaning and optimization utility designed specifically for Soplos Linux.

## 📝 Description

Soplos Sys Cleaner is an advanced system maintenance tool for Soplos Linux distributions (like Boro, Tyron, and Tyson). It safely removes unnecessary files, clears cache, uninstalls old kernels, and optimizes the system while utilizing `dracut.conf.d/soplos.conf` for initramfs integration.

## ✨ Features

- **System Summary**: View at a glance your Soplos variant, active kernel, session type, and uptime.
- **Smart Cleanup of Temporary Files**: 
  - `apt` cache and lists
  - User and root `~/.cache`
  - System logs (`/var/log`)
  - Crash reports
  - `__pycache__` directories automatically detected and cleaned
- **Dual-Layer Scanning**: Separate fast User-level scans and deep Root-level scans to eliminate intrusive password prompts.
- **Disk Space Optimization**: Removes unnecessary packages (`apt autoremove --purge`) and cleans up Flatpak unused runtimes and caches.
- **User Space Management**: Safely empty User Trash and application caches without needing administrative privileges.
- **Old Kernel Removal**: Intelligently identifies and removes old kernels to free up boot partition space, integrating directly with Soplos's system tools.
- **Resource Monitoring**: Tracks CPU usage, RAM utilization, Disk usage, Temperature, and GPU details intuitively.
- **Selective Languages & Docs Cleanup**: Advanced scanner that protects your system locale while allowing removal of unused translations and help files for Gnome, KDE, and XFCE.
- **Smart Selection**: Quickly keep only your active languages and English, marking everything else for deletion.
- **Consolidated Security**: Single password prompt (`pkexec`) for complex cleaning tasks.
- **Slim Modern UI**: Implements Soplos Standard v2.0 with slim tabs and Gtk.HeaderBar matching WebApp Manager.
- **Installed Apps Manager**: Browse all manually installed packages with search, size info and selective uninstall.
- **Snap Support**: Detect and remove old/disabled Snap revisions, consistent with Flatpak cleanup.
- **Firmware Sizes**: Each firmware family shows its disk usage to help decide what to remove.
- **Selective APT Cache**: List and selectively delete individual cached `.deb` files instead of clearing everything at once.
- **Hardware Protection**: Prevents removal of critical network firmwares, GPU firmwares (AMD, Intel, NVIDIA) and active kernels.
- **Full Driver Cleanup**: Detects unnecessary driver packages (GPU, WiFi, VM guest tools, printers, tablets) based on hardware present. After removal, cleans leftover module references in `/etc/modules` and `/etc/modules-load.d/` before regenerating the initramfs — no boot error notifications.
- **Orphaned DKMS Modules**: Detects compiled kernel modules in `/var/lib/dkms/` whose source package is no longer installed and offers to remove them.
- **Orphaned Module References**: Scans `/etc/modules` and `/etc/modules-load.d/` for references to modules from uninstalled packages and shows them in the APT Cache orphaned packages section.
- **Automatic Refresh**: Instant UI updates after cleaning operations.p
- **Universal Scanning**: Deep scan of over 15 critical system paths tailored for Boro, Tyron, and Tyson.
- **One-Click Maintenance**: Cleans everything or just specific sections.
- **Desktop Environment Agnostic**: Designed to fit seamlessly into Soplos distributions running GNOME, KDE Plasma, or XFCE using native-looking GTK interfaces.

## 📸 Screenshots

### User Mode

| Overview | Installed Apps |
| :---: | :---: |
| ![Overview](assets/screenshots/screenshot01.png) | ![Apps](assets/screenshots/screenshot02.png) |

| Flatpak | Snap |
| :---: | :---: |
| ![Flatpak](assets/screenshots/screenshot03.png) | ![Snap](assets/screenshots/screenshot04.png) |

| User Cache | Trash |
| :---: | :---: |
| ![User Cache](assets/screenshots/screenshot05.png) | ![Trash](assets/screenshots/screenshot06.png) |

### Administrator Mode

| Overview | GPU Drivers |
| :---: | :---: |
| ![Overview Root](assets/screenshots/screenshot07.png) | ![GPU Drivers](assets/screenshots/screenshot08.png) |

| Firmwares | Kernels |
| :---: | :---: |
| ![Firmwares](assets/screenshots/screenshot09.png) | ![Kernels](assets/screenshots/screenshot10.png) |

| Languages & Docs | APT Cache |
| :---: | :---: |
| ![Languages](assets/screenshots/screenshot11.png) | ![APT Cache](assets/screenshots/screenshot12.png) |

| Temp Files | System Logs |
| :---: | :---: |
| ![Temp Files](assets/screenshots/screenshot13.png) | ![System Logs](assets/screenshots/screenshot14.png) |

## 🔧 Installation

```bash
# Installation instructions
sudo apt install soplos-sys-cleaner
```

## 🌐 Supported Languages

- 🇪🇸 Spanish (Español)
- 🇬🇧 English
- 🇫🇷 French (Français)
- 🇵🇹 Portuguese (Português)
- 🇩🇪 German (Deutsch)
- 🇮🇹 Italian (Italiano)
- 🇷🇺 Russian (Русский)
- 🇷🇴 Romanian (Română)

## 📄 License

This project is licensed under [GPL-3.0+](https://www.gnu.org/licenses/gpl-3.0.html) (GNU General Public License version 3 or later).

This license guarantees the following freedoms:
- The freedom to use the program for any purpose
- The freedom to study how the program works and modify it
- The freedom to distribute copies of the program
- The freedom to improve the program and publish those improvements

Any derivative work must be distributed under the same license (GPL-3.0+).

For more details, see the LICENSE file or visit [gnu.org/licenses/gpl-3.0](https://www.gnu.org/licenses/gpl-3.0.html).

## 👤 Developer

Developed by Sergi Perich  
Website: https://soplos.org  
Contact: info@soploslinux.com

## 🔗 Links

- [Website](https://soplos.org)
- [Report issues](https://github.com/SoplosLinux/soplos-sys-cleaner/issues)
- [Help](https://soplos.org)

## 📦 Versions

### v1.0.2-5 (12/06/2026)
- Fixed: firmware removal is now permanent — the action purges the owning APT package (`firmware-realtek`, `firmware-amd-graphics`, `firmware-iwlwifi`, etc.) instead of only deleting files from `/lib/firmware/`. Previously, `apt full-upgrade` restored all removed firmware on every system update because the packages were still installed.

### v1.0.2-4 (09/06/2026)
- Fixed: DKMS orphan detector was showing the active NVIDIA driver (and other installed DKMS drivers) as orphaned — caused by a mismatch between the DKMS directory name (`nvidia`) and the actual package name (`nvidia-kernel-dkms`). Added an explicit name map for all known cases.
- Fixed: DKMS orphan detector was not detecting old compiled versions left after a driver upgrade (e.g. nvidia 580.126.20 lingering after upgrade to 580.159.04). Now checks for `/usr/src/<module>-<version>/` presence and compares the installed package version to the DKMS directory version.

### v1.0.2-3 (04/06/2026)
- Added: orphaned DKMS module detection in the Drivers tab — compiled `.ko` files in `/var/lib/dkms/` with no installed source package, removed via `dkms remove` + `dracut -f`.
- Added: orphaned reference scanner covering `/etc/modules`, `/etc/modules-load.d/`, `/etc/modprobe.d/`, systemd unit files, and X11/XDG autostart files — shown in APT Cache → Orphaned packages.
- Added: automatic cleanup of module references in `/etc/modules` and `/etc/modules-load.d/` after driver package removal, before `dracut -f`.
- Added: `clean_module_refs` action disables orphaned systemd services, removes orphaned modprobe.d and X11/XDG autostart files, rebuilds initramfs.
- Fixed: `VBoxClient: the VirtualBox kernel service is not running` notifications after removing VirtualBox guest packages — caused by orphaned `/etc/X11/Xsession.d/98vboxadd-xclient` and `/etc/xdg/autostart/vboxclient.desktop`.
- Fixed: full coverage for VMware (`vmtoolsd.service`, `vmware-vmblock-fuse.service`, `vmware-user.desktop`, `70vmware-user`), NVIDIA (`nvidia-persistenced.service`, `nvidia-hibernate/resume/suspend.service`, `/etc/modprobe.d/nvidia-blacklist-nouveau.conf`), Broadcom (`/etc/modprobe.d/blacklist-bcm43.conf`, `wl.conf`) and Hyper-V daemon services.
- Fixed: users who removed drivers in a previous session can now clean up leftover references from APT Cache → Orphaned packages without reinstalling anything.

### v1.0.2-2 (29/05/2026)
- Added: VM guest tool packages now managed via `systemd-detect-virt` — VirtualBox, VMware, KVM/QEMU (SPICE), Hyper-V, Xen tools shown as removable when not running in that hypervisor.
- Added: printer driver detection for HP, Epson, Canon, Brother, Samsung, Kyocera via USB vendor ID.
- Added: Wacom tablet driver detection via USB vendor ID.
- Added: Broadcom proprietary WiFi driver detection via PCI vendor ID.
- Fixed: Intel GPU packages no longer falsely protected by Intel chipset devices in VMs (new PCI class `03xx` check).
- Fixed: VMware tools shown as removable when running in VMware — was caused by VirtualBox VMSVGA exposing VMware PCI vendor in lspci.
- Fixed: all Drivers tab fixes now apply in production — `root_helper.py` was not updated with `gpu_pci_vendors`/`vm_guest_type`.
- Fixed: `dracut_fw_dirs` now exported from `root_helper`, firmware protection set correctly rebuilt client-side.
- Fixed: progress bar no longer shows 100% during indeterminate operations.
- Fixed: "Select all" checkbox now resets after cleanup in all tabs.

### v1.0.2-1 (17/04/2026)
- Snap tab redesigned with full uninstall support (`snap remove --purge`) and old revisions section, matching Flatpak tab design.
- VM guest detection via `systemd-detect-virt`: KVM, QEMU, VMware, VirtualBox, Hyper-V, Xen, Parallels displayed in Drivers tab label.
- Fixed: kernel removal now runs `dracut -f` and `update-grub` after `apt purge`.
- Fixed: all `apt-get` commands replaced with `apt` throughout the root helper.
- Fixed: 27 untranslated strings added to all 8 language dictionaries.

### v1.0.2 (29/03/2026)
- Added Installed Apps tab with search and selective uninstall via pkexec.
- Added Snap old revisions tab in user mode, consistent with Flatpak.
- Firmware families now show disk usage in the Firmwares tab.
- APT Cache tab now lists individual `.deb` files for selective removal.
- User-mode scan starts automatically on launch.
- Fixed AMD/GPU and KVM/VMware/VirtualBox firmware and driver protection.
- Added "Select all docs" button in the Languages tab.
- Overview cards now follow tab order in both user and root modes.
- Fixed: Flatpak tab redesigned with two sections — installed apps (name, app ID, version, size) and unused runtimes.
- Fixed: Flatpak sizes now read actual disk usage via `du`; `flatpak list --columns=size` always returned 0 for installed items.
- Fixed: Flatpak unused runtime detection delegates to `flatpak uninstall --unused` to correctly handle SDK dependencies, GL extensions and transitive references.
- Fixed: Firmware and kernel packages no longer appear in the Installed Apps tab after root-mode cleanup.
- Fixed: Progress bar no longer stuck at 100%; user scan uses real fractions, root scan uses a continuous pulse animation.

### v1.0.1 (25/03/2026)
- Major Architecture Update: Introduced Dual-Layer Scanning (User vs Root modes) to prevent unnecessary password prompts on startup.
- Added Flatpak unused runtimes cleaning.
- Added specific User Cache (`~/.cache`) and Trash cleanup tabs working without root privileges.
- Dynamic UI tabs that reveal administrative features only after explicit root authorization.
- Fixed repeated `pkexec` password prompts when refreshing UI after cleanup tasks.
- Fixed Kernels tab appearing empty due to IPC data mapping errors.
- Fixed redundant root authentication loops when the application is launched via `sudo`.

### v1.0.0-2 (20/03/2026)
- Fixed: About dialog credits panel on KDE now displays with an opaque dark background and square corners instead of transparent or rounded-corner artifacts.
- About dialog app icon standardized to 48×48 pixels.

### v1.0.0-1 (20/03/2026)
- Added keyboard shortcuts Ctrl+Tab / Ctrl+Shift+Tab to cycle between tabs.
- Added F1 shortcut to open the About dialog.
- Fixed: GNOME HeaderBar now displays with correct dark background matching other Soplos apps.
- Fixed: GNOME CSD window controls (minimize/maximize/close) no longer styled by the global button CSS.

### v1.0.0 (20/03/2026)
- Initial release with Soplos v2.0 Standard Architecture.
- New "Languages & Docs" tab with intelligent locale protection (Gnome/KDE/XFCE support).
- Professional HeaderBar replication mirroring WebApp Manager (Buttons flat and titlebar class).
- Slim and modern tab UI (Soplos Standard v2.0) with custom padding and smaller icons.
- Consolidated `pkexec` prompts for unified administrative tasks.
- Recursive `__pycache__` cleaning support.
- Extended hardware monitoring (Temperature, GPU, Disk).
- Forced network firmware protection to prevent boot issues.
- Precise disk usage calculation using `du -sk`.
- Universal scanner covering over 15 critical system paths.
- Default window size optimized to 920x600.
- Full UI translation in 8 languages (ES, EN, FR, DE, PT, IT, RO, RU).
- Added keyboard shortcuts: Ctrl+W (close), Ctrl+R (rescan), Ctrl+1–7 (tab navigation).
- Scan icon in Overview tab enlarged to 128px.
- Fixed: action buttons now re-enable after failed or cancelled operations.
- Fixed: progress bar now closes after kernel cleanup completes.
- Fixed: translatable strings in GPU Drivers and Firmware tabs corrected to English.
- Fixed: socket files and symlinks (D-Bus, MCP) excluded from Temp Files scanner.
- Fixed: temp file deletion now uses `pkexec` fallback for root-owned files.
- Fixed: APT Cache scanner now includes package lists size (`/var/lib/apt/lists/`).
- Fixed: "Remove orphaned packages" button hidden when no orphans are present.
- Fixed: Languages tab uses lazy loading — widgets created only when tab is opened, eliminating post-scan UI freeze.
- Fixed: system usage metrics timer moved to background thread to prevent interaction lag.
- Improved: `fmt_size()` consolidated in `utils/constants.py`, eliminating duplication across 6 files.
- Improved: duplicate constants and unused functions removed.
- Improved: Overview card strings fully translatable in all 8 languages.

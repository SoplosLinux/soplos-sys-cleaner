# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/en/).

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

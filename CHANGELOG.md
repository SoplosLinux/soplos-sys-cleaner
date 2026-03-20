# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/en/).

## [1.0.0] - 2026-03-20

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

### 🔧 Improved
- Shared utility function `fmt_size()` consolidated in `utils/constants.py`, eliminating duplication across 6 tab files.
- Duplicate constant definitions (`SUPPORTED_LANGUAGES`, `PROTECTED_FIRMWARE`) removed; single source of truth in their respective modules.
- Unused functions removed: `get_autoremove_size_kb()`, `_get_size()`, `get_total_temp_size()`.
- Misplaced and unused imports cleaned up across all UI and scanner modules.
- Logging in `application.py` unified through the `logger` module (replaced `print()` calls).

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

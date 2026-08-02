"""
Desktop environment and display protocol detection.
Adapted to Soplos Sys Cleaner.
"""

import os
import subprocess
from pathlib import Path


class EnvironmentDetector:

    def get_environment_info(self) -> dict:
        return {
            'desktop': self._detect_desktop(),
            'protocol': self._detect_protocol(),
            'theme_type': self._detect_theme_type(),
        }

    def _detect_desktop(self) -> str:
        de = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if 'gnome' in de:
            return 'gnome'
        if 'kde' in de or 'plasma' in de:
            return 'kde'
        if 'xfce' in de:
            return 'xfce'
        session = os.environ.get('DESKTOP_SESSION', '').lower()
        if 'gnome' in session:
            return 'gnome'
        if 'plasma' in session or 'kde' in session:
            return 'kde'
        if 'xfce' in session:
            return 'xfce'
        return 'unknown'

    def _detect_protocol(self) -> str:
        wayland = os.environ.get('WAYLAND_DISPLAY')
        if wayland:
            return 'wayland'
        x11 = os.environ.get('DISPLAY')
        if x11:
            return 'x11'
        return 'unknown'

    def _detect_theme_type(self) -> str:
        """Routed per desktop — these apps run on Tyron (XFCE), Tyson (KDE)
        and Boro (GNOME), and each DE exposes its dark/light preference in a
        completely different place. Ported from soplos-welcome's
        core/environment.py, the one confirmed working across desktops."""
        desktop = self._detect_desktop()
        if desktop == 'xfce':
            return self._detect_xfce_theme()
        if desktop == 'kde':
            return self._detect_kde_theme()
        if desktop == 'gnome':
            return self._detect_gnome_theme()
        return 'light'

    def _detect_xfce_theme(self) -> str:
        # The active GTK theme name is authoritative on XFCE — unlike
        # gsettings' color-scheme key (GNOME-specific, and left at whatever
        # stale default this system had, never updated when the theme
        # changes on XFCE), this reflects the real active theme.
        try:
            result = subprocess.run(
                ['xfconf-query', '-c', 'xsettings', '-p', '/Net/ThemeName'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return 'dark' if 'dark' in result.stdout.lower() else 'light'
        except Exception:
            pass
        return 'light'

    def _detect_kde_theme(self) -> str:
        import configparser
        try:
            kde_config = Path.home() / '.config' / 'kdeglobals'
            if kde_config.exists():
                config = configparser.ConfigParser()
                config.read(kde_config)

                if 'General' in config:
                    color_scheme = config['General'].get('ColorScheme', '').lower()
                    if 'dark' in color_scheme or 'black' in color_scheme:
                        return 'dark'

                if 'Colors:Window' in config:
                    bg_color = config['Colors:Window'].get('BackgroundNormal', '')
                    if bg_color:
                        try:
                            r, g, b = map(int, bg_color.split(','))
                            if (r + g + b) / 3 < 128:
                                return 'dark'
                        except ValueError:
                            pass
        except Exception:
            pass

        try:
            gtk_config = Path.home() / '.config' / 'gtk-3.0' / 'settings.ini'
            if gtk_config.exists():
                config = configparser.ConfigParser()
                config.read(gtk_config)
                if 'Settings' in config:
                    prefer_dark = config['Settings'].get('gtk-application-prefer-dark-theme', '').lower()
                    if prefer_dark in ('1', 'true', 'yes'):
                        return 'dark'
                    theme_name = config['Settings'].get('gtk-theme-name', '').lower()
                    if 'dark' in theme_name:
                        return 'dark'
        except Exception:
            pass
        return 'light'

    def _detect_gnome_theme(self) -> str:
        try:
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                if 'dark' in result.stdout.lower():
                    return 'dark'
                if 'light' in result.stdout.lower():
                    return 'light'
        except Exception:
            pass

        try:
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and 'dark' in result.stdout.lower():
                return 'dark'
        except Exception:
            pass
        return 'light'

    def configure_environment_variables(self):
        """Set environment variables for best GTK integration."""
        protocol = self._detect_protocol()
        if protocol == 'wayland':
            os.environ.setdefault('GDK_BACKEND', 'wayland')
        else:
            os.environ.setdefault('GDK_BACKEND', 'x11')


_detector = None


def get_environment_detector() -> EnvironmentDetector:
    global _detector
    if _detector is None:
        _detector = EnvironmentDetector()
    return _detector

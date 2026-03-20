"""
Desktop environment and display protocol detection.
Adapted to Soplos Sys Cleaner.
"""

import os
import subprocess


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
        try:
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
                capture_output=True, text=True, timeout=2
            )
            if 'dark' in result.stdout.lower():
                return 'dark'
        except Exception:
            pass
        gtk_theme = os.environ.get('GTK_THEME', '').lower()
        if 'dark' in gtk_theme:
            return 'dark'
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

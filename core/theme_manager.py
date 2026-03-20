"""
CSS Theme manager for Soplos Sys Cleaner.
Loads base + light/dark CSS from assets/themes/.
"""

import os
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk


_theme_manager = None


class ThemeManager:

    def __init__(self, assets_path: str):
        self.assets_path = Path(assets_path)
        self.themes_path = self.assets_path / 'themes'
        self.current_theme = 'base'
        self._css_provider = Gtk.CssProvider()

    def load_theme(self, theme_name: str = None) -> str:
        """Load CSS theme. If no name given, auto-detect from environment."""
        if theme_name is None:
            from .environment import get_environment_detector
            env = get_environment_detector()
            theme_name = env._detect_theme_type()  # 'light' or 'dark'

        base_css = self.themes_path / 'base.css'
        theme_css = self.themes_path / f'{theme_name}.css'

        combined_css = ''
        for css_path in [base_css, theme_css]:
            if css_path.exists():
                with open(css_path, 'r', encoding='utf-8') as f:
                    combined_css += f.read() + '\n'

        if combined_css:
            try:
                self._css_provider.load_from_data(combined_css.encode('utf-8'))
                screen = Gdk.Screen.get_default()
                Gtk.StyleContext.add_provider_for_screen(
                    screen,
                    self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                self.current_theme = theme_name
            except Exception as e:
                print(f"[theme] Error loading CSS: {e}")

        return self.current_theme


def get_theme_manager() -> ThemeManager:
    global _theme_manager
    return _theme_manager


def initialize_theming(assets_path: str, theme_name: str = None) -> str:
    global _theme_manager
    _theme_manager = ThemeManager(assets_path)
    return _theme_manager.load_theme(theme_name)

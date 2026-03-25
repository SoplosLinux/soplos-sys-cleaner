"""
Main application class for Soplos Sys Cleaner.
Gtk.Application lifecycle management.
"""

import sys
import os
import signal
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio, Gdk

from .environment import get_environment_detector
from .theme_manager import initialize_theming, get_theme_manager
from .i18n_manager import initialize_i18n, get_available_languages, _, get_current_language
from utils.constants import APPLICATION_NAME, APPLICATION_ID, APPLICATION_VERSION
from utils.logger import logger


class SoplosCleanerApplication(Gtk.Application):
    """Main application class for Soplos Sys Cleaner."""

    def __init__(self):
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.main_window = None
        self.environment_detector = None
        self.theme_manager = None

        self.app_path = Path(__file__).parent.parent
        self.assets_path = self.app_path / 'assets'
        self.locale_path = self.app_path / 'locale'

        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)
        self.connect('command-line', self.on_command_line)
        self.connect('shutdown', self.on_shutdown)

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def on_startup(self, app):
        self.environment_detector = get_environment_detector()
        self.environment_detector.configure_environment_variables()
        env_info = self.environment_detector.get_environment_info()
        os.environ['SOPLOS_DESKTOP'] = env_info['desktop']
        logger.info(f"Desktop: {env_info['desktop']}, Protocol: {env_info['protocol']}")

        initialize_i18n(str(self.locale_path))
        initialize_theming(str(self.assets_path))
        self.theme_manager = get_theme_manager()

        GLib.set_prgname(APPLICATION_ID)
        GLib.set_application_name(_(APPLICATION_NAME))

        icon_path = self.assets_path / 'icons' / 'org.soplos.sys-cleaner.png'
        if icon_path.exists():
            try:
                Gtk.Window.set_default_icon_from_file(str(icon_path))
            except Exception:
                pass

    def on_activate(self, app):
        if self.main_window is None:
            self._create_main_window()
        self.main_window.present()

    def on_command_line(self, app, command_line):
        args = command_line.get_arguments()
        if len(args) > 1:
            for arg in args[1:]:
                if arg in ['--help', '-h']:
                    print(f"Soplos Sys Cleaner {APPLICATION_VERSION}")
                    print("Usage: soplos-sys-cleaner [--help] [--version] [--debug]")
                    return 0
                elif arg in ['--version', '-v']:
                    print(f"Soplos Sys Cleaner {APPLICATION_VERSION}")
                    return 0
                elif arg == '--debug':
                    os.environ['SOPLOS_DEBUG'] = '1'
        self.activate()
        return 0

    def on_shutdown(self, app):
        logger.info("Closing Soplos Sys Cleaner...")

    def _create_main_window(self):
        from ui.main_window import MainWindow
        self.main_window = MainWindow(
            application=self,
            environment_detector=self.environment_detector,
            theme_manager=self.theme_manager,
        )
        self.main_window.connect('destroy', self._on_window_destroy)

    def _on_window_destroy(self, window):
        self.main_window = None
        self.quit()

    def _handle_signal(self, signum, frame):
        GLib.idle_add(self.quit)

    def get_theme_detector(self):
        return self.environment_detector


def create_application() -> SoplosCleanerApplication:
    return SoplosCleanerApplication()


def run_application(argv: list = None) -> int:
    if argv is None:
        argv = sys.argv
    app = create_application()
    try:
        return app.run(argv)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"[app] Error: {e}")
        return 1

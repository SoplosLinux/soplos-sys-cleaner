"""
Main window for Soplos Sys Cleaner.
Follows Soplos v2.0 standard: HeaderBar + Notebook(6 tabs) + ProgressRevealer + Footer.
Compatible with X11, Wayland, GNOME, KDE, XFCE.
"""

import os
import sys
import shutil
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

from core.i18n_manager import _
from utils.constants import (
    APPLICATION_NAME, APPLICATION_VERSION,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT
)
from utils.logger import logger

from ui.tabs.overview_tab import OverviewTab
from ui.tabs.drivers_tab import DriversTab
from ui.tabs.firmware_tab import FirmwareTab
from ui.tabs.kernels_tab import KernelsTab
from ui.tabs.cache_tab import CacheTab
from ui.tabs.temp_tab import TempTab
from ui.tabs.locales_tab import LocalesTab
from ui.tabs.user_cache_tab import UserCacheTab
from ui.tabs.trash_tab import TrashTab
from ui.tabs.flatpak_tab import FlatpakTab
from ui.tabs.logs_tab import LogsTab


class MainWindow(Gtk.ApplicationWindow):
    """
    Main window for Soplos Sys Cleaner.
    Hierarchy: HeaderBar | VBox → Notebook → ProgressRevealer → Footer
    """

    def __init__(self, application, environment_detector, theme_manager):
        super().__init__(application=application)
        self.application = application
        self.env_detector = environment_detector
        self.theme_manager = theme_manager

        self._scan_results = {}

        self.set_title(_(APPLICATION_NAME))
        self.set_default_size(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)
        self.get_style_context().add_class('soplos-window')

        self._create_header_bar()
        self._setup_ui()
        self._setup_shortcuts()
        self.show_all()
        self.progress_revealer.set_reveal_child(False)
        self.connect('destroy', self._on_self_destroy)

    def _on_self_destroy(self, *args):
        """Pre-destruction cleanup."""
        self._stop_root_session()

    # ─────────────────────────── HeaderBar ───────────────────────────

    def _create_header_bar(self):
        """Match Soplos Standard: SSD for XFCE/KDE, CSD for GNOME."""
        desktop_env = 'unknown'
        try:
            if self.env_detector:
                info = self.env_detector.get_environment_info()
                desktop_env = info.get('desktop', 'unknown').lower()
        except Exception:
            pass

        # XFCE and KDE/Plasma work best with native window decorations (SSD)
        if desktop_env in ['xfce', 'kde', 'plasma']:
            self.header = None
            return

        # For GNOME and others, use Client-Side Decorations (CSD)
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.set_title(_(APPLICATION_NAME))
        self.header.set_decoration_layout("menu:minimize,maximize,close")
        self.header.get_style_context().add_class('titlebar')
        self.set_titlebar(self.header)

        # Scan button (native style, no .flat — matching all other Soplos apps)
        self.scan_btn_header = Gtk.Button()
        self.scan_btn_header.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
        self.scan_btn_header.set_tooltip_text(_("Scan system"))
        self.scan_btn_header.connect('clicked', self._on_scan_clicked)
        self.header.pack_start(self.scan_btn_header)

    # ─────────────────────────── Main UI ───────────────────────────

    def _setup_ui(self):
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_vbox)

        # Notebook with 6 tabs
        self.notebook = Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)
        self.notebook.set_scrollable(True)
        self.notebook.set_show_border(False)
        
        # Soplos Standard: Apply slim tab styling
        self._apply_notebook_custom_css()
        
        main_vbox.pack_start(self.notebook, True, True, 0)

        # Instantiate tabs
        self.overview_tab = OverviewTab(self)
        self.user_cache_tab = UserCacheTab(self)
        self.trash_tab = TrashTab(self)
        self.flatpak_tab = FlatpakTab(self)
        # Root-only tabs
        self.drivers_tab = DriversTab(self)
        self.firmware_tab = FirmwareTab(self)
        self.kernels_tab = KernelsTab(self)
        self.cache_tab = CacheTab(self)
        self.temp_tab = TempTab(self)
        self.locales_tab = LocalesTab(self)
        self.logs_tab = LogsTab(self)

        # User tabs always visible
        user_tabs = [
            (self.overview_tab,    _("Overview"),      'preferences-system'),
            (self.user_cache_tab,  _("User Cache"),    'folder'),
            (self.trash_tab,       _("Trash"),         'user-trash-full'),
            (self.flatpak_tab,     _("Flatpak"),       'package-x-generic'),
        ]

        # Root tabs — added dynamically after root scan if running as user
        self._root_tab_definitions = [
            (self.drivers_tab,   _("GPU Drivers"),   'video-display'),
            (self.firmware_tab,  _("Firmwares"),     'drive-harddisk'),
            (self.kernels_tab,   _("Kernels"),       'media-flash'),
            (self.locales_tab,   _("Languages"),     'locale'),
            (self.cache_tab,     _("APT Cache"),     'system-software-install'),
            (self.temp_tab,      _("Temp Files"),    'user-trash-full'),
            (self.logs_tab,      _("System Logs"),   'text-x-script'),
        ]

        tab_definitions = user_tabs + (self._root_tab_definitions if os.geteuid() == 0 else [])

        for widget, label_text, icon_name in tab_definitions:
            self._append_tab(widget, label_text, icon_name)

        # Progress Revealer (Soplos standard)
        self.progress_revealer = Gtk.Revealer()
        self.progress_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        revealer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        revealer_box.set_margin_start(20)
        revealer_box.set_margin_end(20)
        revealer_box.set_margin_top(8)
        revealer_box.set_margin_bottom(8)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        revealer_box.pack_start(self.progress_bar, False, False, 0)

        self.progress_label = Gtk.Label(label=_("Ready"))
        self.progress_label.get_style_context().add_class('dim-label')
        self.progress_label.set_halign(Gtk.Align.START)
        revealer_box.pack_start(self.progress_label, False, False, 0)

        self.progress_revealer.add(revealer_box)
        main_vbox.pack_start(self.progress_revealer, False, False, 0)

        # Footer (Soplos standard)
        self._create_footer(main_vbox)

    def _create_footer(self, parent):
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.get_style_context().add_class('soplos-footer')
        footer.set_margin_start(15)
        footer.set_margin_end(15)
        footer.set_margin_top(5)
        footer.set_margin_bottom(5)
        parent.pack_end(footer, False, False, 0)

        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.get_style_context().add_class('dim-label')
        self._update_footer()
        footer.pack_start(self.status_label, True, True, 0)

        version_label = Gtk.Label(label=f"v{APPLICATION_VERSION}")
        version_label.get_style_context().add_class('dim-label')
        footer.pack_end(version_label, False, False, 0)

    def _update_footer(self):
        if self.env_detector:
            info = self.env_detector.get_environment_info()
            desktop = info.get('desktop', 'unknown').upper()
            protocol = info.get('protocol', 'unknown').upper()
            base = _("Running on {} ({})").format(desktop, protocol)
            if os.geteuid() == 0:
                base += _(" — Administrator mode")
            self.status_label.set_text(base)

    def _get_pkexec_env(self):
        """Returns list of "VAR=VALUE" for essential environment variables."""
        important_vars = [
            'DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
            'WAYLAND_DISPLAY', 'XDG_CURRENT_DESKTOP', 'XDG_SESSION_TYPE',
            'SOPLOS_DESKTOP', 'LANG', 'HOME', 'PATH', 'GDK_BACKEND', 'GTK_THEME',
        ]
        ev = [f"{v}={os.environ[v]}" for v in important_vars if v in os.environ]
        ev += ['NO_AT_BRIDGE=1', 'GSETTINGS_BACKEND=memory', 'GIO_USE_VFS=local']
        return ev

    def _relaunch_as_root(self):
        """Relaunch the application with pkexec, propagating the user environment."""
        env_vars = self._get_pkexec_env()
        script_path = str(Path(__file__).resolve().parent.parent / 'main.py')
        pkexec_path = shutil.which('pkexec') or 'pkexec'
        cmd = [pkexec_path, 'env'] + env_vars + [sys.executable, script_path]
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            logger.error(f"Failed to relaunch as root: {e}")

    def _apply_notebook_custom_css(self):
        """Apply Soplos Standard slim tab styling (matching Welcome)."""
        css_provider = Gtk.CssProvider()
        css_data = """
        notebook > header {
            min-height: 20px;
            padding: 0px 0;
        }

        notebook > header > tabs > tab {
            min-height: 20px;
            padding: 8px 12px;
        }

        notebook > header > tabs > tab label {
            padding: 0;
            color: inherit;
        }

        notebook > header > tabs > tab:checked label {
            color: @theme_fg_color;
        }

        treeview header button {
            padding: 4px 6px;
            min-height: 0;
        }

        """
        try:
            css_provider.load_from_data(css_data.encode('utf-8'))
            screen = Gdk.Screen.get_default()
            style_context = Gtk.StyleContext()
            style_context.add_provider_for_screen(
                screen,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            logger.info("Standard notebook CSS applied successfully")
        except Exception as e:
            logger.error(f"Error applying custom CSS: {e}")

    # ─────────────────────────── Shortcuts ───────────────────────────

    def _setup_shortcuts(self):
        accel = Gtk.AccelGroup()
        self.add_accel_group(accel)

        def bind(key, mask, cb):
            mod = getattr(Gdk.ModifierType, f'{mask}_MASK') if mask else 0
            keyval = Gdk.keyval_from_name(key)
            accel.connect(keyval, mod, Gtk.AccelFlags.VISIBLE, lambda *a: cb())

        bind('q', 'CONTROL', lambda: self.application.quit())
        bind('w', 'CONTROL', lambda: self.application.quit())
        bind('r', 'CONTROL', self._on_scan_clicked)
        bind('F5', None, self._on_scan_clicked)
        # Ctrl+Shift+R — root scan (only meaningful when not already root)
        accel.connect(
            Gdk.keyval_from_name('r'),
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
            Gtk.AccelFlags.VISIBLE,
            lambda *a: self.start_root_scan()
        )
        bind('F1', None, self._show_about)
        # Tab navigation: Ctrl+1..7
        for i in range(7):
            idx = i
            bind(str(i + 1), 'CONTROL', lambda n=idx: self.notebook.set_current_page(n))

        # Ctrl+Tab / Ctrl+Shift+Tab via key-press-event (AccelGroup can't catch Tab)
        self.connect('key-press-event', self._on_key_press)

    def _show_about(self):
        dialog = Gtk.AboutDialog()
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_program_name(_(APPLICATION_NAME))
        dialog.set_version(APPLICATION_VERSION)
        dialog.set_comments(_("Advanced system cleaner and optimizer for Soplos Linux."))
        dialog.set_website("https://soplos.org")
        dialog.set_website_label("soplos.org")
        dialog.set_authors(["Sergi Perich <info@soploslinux.com>"])
        dialog.set_license_type(Gtk.License.GPL_3_0)
        icon_path = Path(__file__).parent.parent / 'assets' / 'icons' / '64x64' / 'org.soplos.sys-cleaner.png'
        if icon_path.exists():
            dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon_path), 48, 48, True))
        _about_css = Gtk.CssProvider()
        _about_css.load_from_data(b"""
            dialog, messagedialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            dialog .background, messagedialog .background {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            dialog > box, messagedialog > box {
                background-color: #2b2b2b;
            }
            dialog label, messagedialog label {
                color: #ffffff;
            }
            dialog button, messagedialog button {
                background-image: none;
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 14px;
                box-shadow: none;
            }
            dialog button:hover, messagedialog button:hover {
                background-color: #444444;
                border-color: #ff8800;
            }
            dialog stackswitcher button {
                border-radius: 100px;
                background-color: #2b2b2b;
                background-image: none;
                border: 1px solid #3c3c3c;
                font-weight: normal;
                padding: 4px 16px;
                box-shadow: none;
                color: #ffffff;
            }
            dialog stackswitcher button:hover {
                background-color: #444444;
                border-color: #ff8800;
            }
            dialog stackswitcher button:checked {
                background-color: #444444;
                color: #ffffff;
            }
            dialog scrolledwindow,
            dialog scrolledwindow viewport {
                background-color: #2b2b2b;
                border-radius: 0;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), _about_css,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        dialog.run()
        dialog.destroy()

    def _on_key_press(self, widget, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        shift = event.state & Gdk.ModifierType.SHIFT_MASK
        if ctrl and event.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            n = self.notebook.get_n_pages()
            current = self.notebook.get_current_page()
            if shift:
                self.notebook.set_current_page((current - 1) % n)
            else:
                self.notebook.set_current_page((current + 1) % n)
            return True
        return False

    # ─────────────────────────── Public API ───────────────────────────

    def set_ui_state(self, message: str, fraction: float = None, pulse: bool = False, visible: bool = True):
        """Update progress bar and label. Thread-safe via GLib.idle_add."""
        def _update():
            self.progress_label.set_text(message)
            if pulse:
                self.progress_bar.pulse()
            elif fraction is not None:
                self.progress_bar.set_fraction(fraction)
            self.progress_revealer.set_reveal_child(visible)
        GLib.idle_add(_update)

    def _append_tab(self, widget, label_text, icon_name):
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        tab_box.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU), False, False, 0)
        tab_box.pack_start(Gtk.Label(label=label_text), False, False, 0)
        tab_box.show_all()
        self.notebook.append_page(widget, tab_box)
        widget.show()

    def _ensure_root_tabs_visible(self):
        """Add root tabs to the notebook if not already present."""
        existing = [self.notebook.get_nth_page(i) for i in range(self.notebook.get_n_pages())]
        for widget, label_text, icon_name in self._root_tab_definitions:
            if widget not in existing:
                self._append_tab(widget, label_text, icon_name)

    def _on_scan_clicked(self, *args):
        self.start_scan()

    def start_scan(self):
        """Launch the appropriate scan based on privilege level."""
        if os.geteuid() == 0:
            self.start_root_scan()
        else:
            self.start_user_scan()

    def start_user_scan(self):
        """Scan user-accessible data: ~/.cache, trash, flatpak."""
        if hasattr(self, 'scan_btn_header'):
            self.scan_btn_header.set_sensitive(False)
        self.set_ui_state(_("Scanning user data..."), pulse=True, visible=True)

        def do_scan():
            results = {}
            try:
                GLib.idle_add(self.set_ui_state, _("Scanning user cache..."), None, True, True)
                from scanner.user_cache import get_user_cache_entries
                results['user_cache_entries'] = get_user_cache_entries()

                GLib.idle_add(self.set_ui_state, _("Scanning trash..."), None, True, True)
                from scanner.trash import get_trash_info
                results['trash_info'] = get_trash_info()

                GLib.idle_add(self.set_ui_state, _("Scanning Flatpak..."), None, True, True)
                from scanner.flatpak import get_unused_flatpak_entries
                results['flatpak_entries'] = get_unused_flatpak_entries()

            except Exception as e:
                logger.error(f"User scan error: {e}")
                results['error'] = str(e)

            GLib.idle_add(self._on_user_scan_done, results)

        threading.Thread(target=do_scan, daemon=True).start()

    def _on_user_scan_done(self, results):
        if hasattr(self, 'scan_btn_header'):
            self.scan_btn_header.set_sensitive(True)
        if 'error' in results:
            self.set_ui_state(_("Scan error: {}").format(results['error']), fraction=0, visible=True)
            return
        self.set_ui_state(_("Scan completed"), fraction=1.0, visible=True)
        GLib.timeout_add_seconds(3, lambda: self.set_ui_state("", visible=False))

        self._scan_results.update(results)
        self.overview_tab.populate(self._scan_results)
        self.user_cache_tab.populate(results)
        self.trash_tab.populate(results)
        self.flatpak_tab.populate(results)

    def start_root_scan(self):
        """Launch persistent root helper via pkexec (one auth), send scan command."""
        if hasattr(self, 'scan_btn_header'):
            self.scan_btn_header.set_sensitive(False)
        self.set_ui_state(_("Scanning system (administrator)..."), pulse=True, visible=True)

        def do_scan():
            import json as _json
            try:
                proc = getattr(self, '_root_process', None)
                if proc is None or proc.poll() is not None:
                    script = str(Path(__file__).resolve().parent.parent / 'scanner' / 'root_helper.py')
                    env_vars = self._get_pkexec_env()

                    if os.geteuid() == 0:
                        cmd = ['env'] + env_vars + [sys.executable, script]
                    else:
                        cmd = ['pkexec', 'env'] + env_vars + [sys.executable, script]
                        
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True, bufsize=1
                    )
                    self._root_process = proc

                # Send scan command and wait for result
                proc.stdin.write(_json.dumps({'action': 'scan'}) + '\n')
                proc.stdin.flush()
                line = proc.stdout.readline()

                if not line:
                    GLib.idle_add(self._on_root_scan_done, {'error': _("Authentication cancelled.")})
                    return

                results = _json.loads(line)

            except Exception as e:
                logger.error(f"Root scan error: {e}")
                GLib.idle_add(self._on_root_scan_done, {'error': str(e)})
                return

            GLib.idle_add(self._on_root_scan_done, results)

        threading.Thread(target=do_scan, daemon=True).start()

    def run_root_action(self, action_dict, callback):
        """Send a command to the persistent root process. No password prompt."""
        import json as _json

        def do_action():
            try:
                proc = getattr(self, '_root_process', None)
                if proc is None or proc.poll() is not None:
                    GLib.idle_add(callback, {'success': False, 'error': _("No active root session. Scan as administrator first.")})
                    return
                proc.stdin.write(_json.dumps(action_dict) + '\n')
                proc.stdin.flush()
                line = proc.stdout.readline()
                result = _json.loads(line) if line else {'success': False, 'error': 'No response'}
            except Exception as e:
                result = {'success': False, 'error': str(e)}
            GLib.idle_add(callback, result)

        threading.Thread(target=do_action, daemon=True).start()

    def _stop_root_session(self):
        import json as _json
        proc = getattr(self, '_root_process', None)
        if proc and proc.poll() is None:
            try:
                proc.stdin.write(_json.dumps({'action': 'exit'}) + '\n')
                proc.stdin.flush()
            except Exception:
                pass
        self._root_process = None

    def _on_root_scan_done(self, results):
        if hasattr(self, 'scan_btn_header'):
            self.scan_btn_header.set_sensitive(True)
        if 'error' in results:
            self.set_ui_state(_("Scan error: {}").format(results['error']), fraction=0, visible=True)
            return
        # Add root tabs to notebook if running as user (first time)
        self._ensure_root_tabs_visible()

        self.set_ui_state(_("Scan completed"), fraction=1.0, visible=True)
        GLib.timeout_add_seconds(3, lambda: self.set_ui_state("", visible=False))

        # Deserialize namedtuple-like objects from JSON dicts
        try:
            from scanner.hardware import is_firmware_protected
            results['is_firmware_protected'] = is_firmware_protected

            from scanner.packages import PackageInfo
            results['unnecessary_pkgs'] = [
                PackageInfo(name=p['name'], installed_size=p['installed_size'], description=p['description'], vendor=p['vendor'])
                for p in results.get('unnecessary_pkgs', [])
            ]
            from scanner.kernels import KernelInfo
            results['kernels'] = [
                KernelInfo(version=k['version'], is_active=k['is_active'],
                           has_headers=k['has_headers'], has_src=k['has_src'],
                           image_pkg=k['image_pkg'], headers_pkg=k['headers_pkg'],
                           src_pkg=k['src_pkg'], size_kb=k['size_kb'])
                for k in results.get('kernels', [])
            ]
            from scanner.temp_files import TempEntry
            results['temp_entries'] = [
                TempEntry(path=e['path'], size_bytes=e['size_bytes'],
                          age_days=e['age_days'], is_dir=e['is_dir'])
                for e in results.get('temp_entries', [])
            ]
            from scanner.locales import LocaleEntry, DocEntry
            results['locales'] = [
                LocaleEntry(code=l['code'], name=l['name'], paths=tuple(l['paths']),
                            size_kb=l['size_kb'], category=l['category'])
                for l in results.get('locales', [])
            ]
            results['docs_summary'] = [
                DocEntry(name=d['name'], path=d['path'], size_kb=d['size_kb'], type=d['type'])
                for d in results.get('docs_summary', [])
            ]
        except Exception as e:
            logger.error(f"Error deserializing root scan results: {e}")

        self._scan_results.update(results)
        self.overview_tab.populate(self._scan_results)
        self.drivers_tab.populate(results)
        self.firmware_tab.populate(results)
        self.kernels_tab.populate(results)
        self.cache_tab.populate(results)
        self.temp_tab.populate(results)
        self.locales_tab.populate(results)
        self.logs_tab.populate(results)

"""
Main window for Soplos Sys Cleaner.
Follows Soplos v2.0 standard: HeaderBar + Notebook(6 tabs) + ProgressRevealer + Footer.
Compatible with X11, Wayland, GNOME, KDE, XFCE.
"""

import threading

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

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
        self.drivers_tab = DriversTab(self)
        self.firmware_tab = FirmwareTab(self)
        self.kernels_tab = KernelsTab(self)
        self.cache_tab = CacheTab(self)
        self.temp_tab = TempTab(self)
        self.locales_tab = LocalesTab(self)

        tab_definitions = [
            (self.overview_tab,  _("Overview"),      'preferences-system'),
            (self.drivers_tab,   _("GPU Drivers"),   'video-display'),
            (self.firmware_tab,  _("Firmwares"),     'drive-harddisk'),
            (self.kernels_tab,   _("Kernels"),       'media-flash'),
            (self.locales_tab,   _("Languages"),     'locale'),
            (self.cache_tab,     _("APT Cache"),     'system-software-install'),
            (self.temp_tab,      _("Temp Files"),    'user-trash-full'),
        ]

        for widget, label_text, icon_name in tab_definitions:
            tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            lbl = Gtk.Label(label=label_text)
            tab_box.pack_start(icon, False, False, 0)
            tab_box.pack_start(lbl, False, False, 0)
            tab_box.show_all()
            self.notebook.append_page(widget, tab_box)

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
            self.status_label.set_text(_("Running on {} ({})").format(desktop, protocol))

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
        # Tab navigation: Ctrl+1..7
        for i in range(7):
            idx = i
            bind(str(i + 1), 'CONTROL', lambda n=idx: self.notebook.set_current_page(n))

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

    def _on_scan_clicked(self, *args):
        self.start_scan()

    def start_scan(self):
        """Launch full system scan in background thread."""
        if hasattr(self, 'scan_btn_header'):
            self.scan_btn_header.set_sensitive(False)
        self.set_ui_state(_("Scanning system..."), pulse=True, visible=True)

        def do_scan():
            results = {}
            try:
                from scanner.hardware import get_gpu_vendors, get_all_firmware_families, is_firmware_protected
                from scanner.packages import get_unnecessary_gpu_packages
                from scanner.kernels import get_installed_kernels
                from scanner.cache import get_apt_cache_info, get_autoremove_packages
                from scanner.temp_files import get_temp_entries

                GLib.idle_add(self.set_ui_state, _("Detecting hardware..."), None, True, True)
                info = self.env_detector.get_environment_info()
                results['desktop'] = info.get('desktop', 'unknown')
                results['gpu_vendors'] = get_gpu_vendors()

                GLib.idle_add(self.set_ui_state, _("Scanning GPU drivers..."), None, True, True)
                results['unnecessary_pkgs'] = get_unnecessary_gpu_packages(results['gpu_vendors'])

                GLib.idle_add(self.set_ui_state, _("Scanning firmwares..."), None, True, True)
                results['firmware_families'] = get_all_firmware_families()
                results['is_firmware_protected'] = is_firmware_protected

                GLib.idle_add(self.set_ui_state, _("Scanning kernels..."), None, True, True)
                results['kernels'] = get_installed_kernels()

                GLib.idle_add(self.set_ui_state, _("Scanning APT cache..."), None, True, True)
                results['apt_cache'] = get_apt_cache_info()
                results['autoremove_pkgs'] = get_autoremove_packages()

                GLib.idle_add(self.set_ui_state, _("Scanning temporary files..."), None, True, True)
                results['temp_entries'] = get_temp_entries(min_age_days=0.0)

                GLib.idle_add(self.set_ui_state, _("Scanning languages and docs..."), None, True, True)
                from scanner.locales import get_locales_info, get_docs_summary
                results['locales'] = get_locales_info(results.get('desktop', 'unknown'))
                results['docs_summary'] = get_docs_summary()

            except Exception as e:
                logger.error(f"Scan error: {e}")
                results['error'] = str(e)

            GLib.idle_add(self._on_scan_done, results)

        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_done(self, results):
        self._scan_results = results
        if hasattr(self, 'scan_btn_header'):
            self.scan_btn_header.set_sensitive(True)

        if 'error' in results:
            self.set_ui_state(_("Error during scan: {}").format(results['error']), fraction=0, visible=True)
            return

        self.set_ui_state(_("Scan completed"), fraction=1.0, visible=True)
        GLib.timeout_add_seconds(3, lambda: self.set_ui_state("", visible=False))

        # Populate all tabs
        self.overview_tab.populate(results)
        self.drivers_tab.populate(results)
        self.firmware_tab.populate(results)
        self.kernels_tab.populate(results)
        self.cache_tab.populate(results)
        self.temp_tab.populate(results)
        self.locales_tab.populate(results)

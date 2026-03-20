"""
APT Cache tab: clear apt cache and autoremovable packages.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class CacheTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.parent = parent_window
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self._build_ui()

    def _build_ui(self):
        # APT Cache card
        apt_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        apt_card.get_style_context().add_class('summary-card')

        apt_title = Gtk.Label()
        apt_title.set_markup(f"<b>{_('APT Package Cache')}</b>")
        apt_title.set_halign(Gtk.Align.START)
        apt_card.pack_start(apt_title, False, False, 0)

        self.apt_info_label = Gtk.Label(label=_("Click «Scan» to view cache status"))
        self.apt_info_label.set_halign(Gtk.Align.START)
        apt_card.pack_start(self.apt_info_label, False, False, 0)

        self.clean_cache_btn = Gtk.Button()
        b1 = Gtk.Box(spacing=6)
        b1.pack_start(Gtk.Image.new_from_icon_name('edit-clear', Gtk.IconSize.BUTTON), False, False, 0)
        b1.pack_start(Gtk.Label(label=_("Clean APT Cache")), False, False, 0)
        self.clean_cache_btn.add(b1)
        self.clean_cache_btn.connect('clicked', self._on_clean_cache)
        apt_card.pack_start(self.clean_cache_btn, False, False, 0)
        self.pack_start(apt_card, False, False, 0)

        # Orphaned Packages card
        auto_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        auto_card.get_style_context().add_class('summary-card')

        auto_title = Gtk.Label()
        auto_title.set_markup(f"<b>{_('Orphaned Packages')}</b>")
        auto_title.set_halign(Gtk.Align.START)
        auto_card.pack_start(auto_title, False, False, 0)

        self.autoremove_label = Gtk.Label(label=_("Click «Scan» to view orphaned packages"))
        self.autoremove_label.set_halign(Gtk.Align.START)
        auto_card.pack_start(self.autoremove_label, False, False, 0)

        self.orphan_scroll = Gtk.ScrolledWindow()
        self.orphan_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        auto_card.pack_start(self.orphan_scroll, True, True, 0)

        self.orphan_list = Gtk.ListBox()
        self.orphan_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.orphan_scroll.add(self.orphan_list)
        self.orphan_scroll.set_no_show_all(True)

        self.autoremove_btn = Gtk.Button()
        b2 = Gtk.Box(spacing=6)
        b2.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        b2.pack_start(Gtk.Label(label=_("Remove Orphaned Packages")), False, False, 0)
        self.autoremove_btn.add(b2)
        self.autoremove_btn.get_style_context().add_class('destructive-action')
        self.autoremove_btn.connect('clicked', self._on_autoremove)
        self.autoremove_btn.set_sensitive(False)
        auto_card.pack_start(self.autoremove_btn, False, False, 0)

        self.pack_start(auto_card, True, True, 0)
        self.show_all()

    def populate(self, results: dict):
        apt_info = results.get('apt_cache', {})
        size = apt_info.get('size_bytes', 0)
        count = apt_info.get('deb_count', 0)
        lists_size = apt_info.get('lists_size_bytes', 0)
        total = size + lists_size
        if count > 0:
            self.apt_info_label.set_text(
                _("{} cached .deb files — {} | Package lists: {}").format(count, _fmt_size(size), _fmt_size(lists_size))
            )
        else:
            self.apt_info_label.set_text(
                _("No cached .deb files | Package lists: {}").format(_fmt_size(lists_size))
            )

        # Orphan packages
        for row in self.orphan_list.get_children():
            self.orphan_list.remove(row)

        orphans = results.get('autoremove_pkgs', [])
        if not orphans:
            self.autoremove_label.set_text(_("No orphaned packages"))
            self.orphan_scroll.hide()
            self.autoremove_btn.hide()
        else:
            self.orphan_scroll.show()
            for pkg in orphans:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(label=pkg)
                label.set_halign(Gtk.Align.START)
                label.set_margin_start(12)
                label.set_margin_top(4)
                label.set_margin_bottom(4)
                row.add(label)
                self.orphan_list.add(row)
            self.autoremove_label.set_text(
                _("{} orphaned package(s) detected").format(len(orphans))
            )
            self.autoremove_btn.set_sensitive(True)
            self.autoremove_btn.show()

        self.orphan_list.show_all()

    def _on_clean_cache(self, btn):
        btn.set_sensitive(False)
        def do_clean():
            from cleaner.remover import clean_apt_cache
            self.parent.set_ui_state(_("Cleaning APT cache..."), pulse=True)
            success, msg = clean_apt_cache()
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))
        threading.Thread(target=do_clean, daemon=True).start()

    def _on_autoremove(self, btn):
        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove orphaned packages?")
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)
        def do_autoremove():
            from cleaner.remover import autoremove_packages
            self.parent.set_ui_state(_("Removing orphaned packages..."), pulse=True)
            success, msg = autoremove_packages()
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))
        threading.Thread(target=do_autoremove, daemon=True).start()

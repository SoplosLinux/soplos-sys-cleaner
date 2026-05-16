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
        self._deb_checkboxes = {}
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

        deb_btn_box = Gtk.Box(spacing=8)

        self.clean_cache_btn = Gtk.Button()
        b1 = Gtk.Box(spacing=6)
        b1.pack_start(Gtk.Image.new_from_icon_name('edit-clear', Gtk.IconSize.BUTTON), False, False, 0)
        b1.pack_start(Gtk.Label(label=_("Clean all")), False, False, 0)
        self.clean_cache_btn.add(b1)
        self.clean_cache_btn.connect('clicked', self._on_clean_cache)
        deb_btn_box.pack_start(self.clean_cache_btn, False, False, 0)

        self.remove_selected_btn = Gtk.Button()
        b1s = Gtk.Box(spacing=6)
        b1s.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        b1s.pack_start(Gtk.Label(label=_("Remove selected")), False, False, 0)
        self.remove_selected_btn.add(b1s)
        self.remove_selected_btn.get_style_context().add_class('destructive-action')
        self.remove_selected_btn.connect('clicked', self._on_remove_selected_debs)
        self.remove_selected_btn.set_sensitive(False)
        deb_btn_box.pack_start(self.remove_selected_btn, False, False, 0)

        apt_card.pack_start(deb_btn_box, False, False, 0)

        # .deb file list
        deb_scroll = Gtk.ScrolledWindow()
        deb_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        deb_scroll.set_min_content_height(120)
        apt_card.pack_start(deb_scroll, True, True, 0)
        self.deb_list = Gtk.ListBox()
        self.deb_list.set_selection_mode(Gtk.SelectionMode.NONE)
        deb_scroll.add(self.deb_list)

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
        if count > 0:
            self.apt_info_label.set_text(
                _("{} cached .deb files — {} | Package lists: {}").format(count, _fmt_size(size), _fmt_size(lists_size))
            )
        else:
            self.apt_info_label.set_text(
                _("No cached .deb files | Package lists: {}").format(_fmt_size(lists_size))
            )

        # Fill .deb list
        for row in self.deb_list.get_children():
            self.deb_list.remove(row)
        self._deb_checkboxes.clear()

        debs = results.get('apt_cache_debs', [])
        for deb in debs:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(spacing=12)
            row_box.set_margin_start(8)
            row_box.set_margin_end(8)
            row_box.set_margin_top(4)
            row_box.set_margin_bottom(4)

            check = Gtk.CheckButton()
            check.connect('toggled', self._on_deb_toggled)
            self._deb_checkboxes[deb['path']] = check
            row_box.pack_start(check, False, False, 0)

            lbl = Gtk.Label(label=deb['name'])
            lbl.set_halign(Gtk.Align.START)
            lbl.set_ellipsize(3)
            row_box.pack_start(lbl, True, True, 0)

            size_lbl = Gtk.Label(label=_fmt_size(deb['size_bytes']))
            size_lbl.get_style_context().add_class('dim-label')
            size_lbl.set_width_chars(9)
            size_lbl.set_halign(Gtk.Align.END)
            row_box.pack_end(size_lbl, False, False, 0)

            row.add(row_box)
            self.deb_list.add(row)
        self.deb_list.show_all()

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

    def _on_deb_toggled(self, check):
        self.remove_selected_btn.set_sensitive(
            any(c.get_active() for c in self._deb_checkboxes.values())
        )

    def _on_remove_selected_debs(self, btn):
        selected = [path for path, check in self._deb_checkboxes.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected .deb files?")
        )
        dialog.format_secondary_text(_("{} file(s) will be deleted from the APT cache.").format(len(selected)))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)
        self.parent.set_ui_state(_("Removing selected .deb files..."), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _("Selected .deb files removed.") if success else result.get('error', _("Unknown error"))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'delete_paths', 'paths': selected}, on_done)

    def _on_clean_cache(self, btn):
        btn.set_sensitive(False)
        self.parent.set_ui_state(_("Cleaning APT cache..."), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _("APT cache cleaned successfully.") if success else f"Error: {result.get('stderr', '')}"
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'apt_clean'}, on_done)

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
        self.parent.set_ui_state(_("Removing orphaned packages..."), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _("Orphaned packages removed.") if success else f"Error: {result.get('stderr', '')}"
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'apt_autoremove'}, on_done)

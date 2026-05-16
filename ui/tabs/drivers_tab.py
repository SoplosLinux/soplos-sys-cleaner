"""
Drivers tab: shows GPU driver packages that can be safely removed.
User selects which ones to purge.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class DriversTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._packages = []
        self._checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        # Top info bar
        info_box = Gtk.Box(spacing=10)
        info_box.set_margin_start(12)
        info_box.set_margin_end(12)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(8)

        self.hw_label = Gtk.Label(label=_("Detected hardware: —"))
        self.hw_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.hw_label, True, True, 0)

        self.select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.select_all_btn.connect('toggled', self._on_select_all)
        info_box.pack_end(self.select_all_btn, False, False, 0)
        self.pack_start(info_box, False, False, 0)

        # Package list in card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class('summary-card')
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        card.pack_start(scroll, True, True, 0)
        self.pack_start(card, True, True, 0)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self.list_box)

        # Action buttons
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(12)
        actions.set_margin_bottom(12)

        self.remove_btn = Gtk.Button()
        btn_box = Gtk.Box(spacing=6)
        btn_box.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        btn_box.pack_start(Gtk.Label(label=_("Remove Selected")), False, False, 0)
        self.remove_btn.add(btn_box)
        self.remove_btn.get_style_context().add_class('destructive-action')
        self.remove_btn.connect('clicked', self._on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        actions.pack_start(self.remove_btn, False, False, 0)

        self.pack_start(actions, False, False, 0)
        self.show_all()

    def populate(self, results: dict):
        # Clear list
        for row in self.list_box.get_children():
            self.list_box.remove(row)
        self._checkboxes.clear()

        hw_summary = results.get('hardware_summary', [])
        self.hw_label.set_text(
            _("Detected hardware: {}").format(', '.join(hw_summary) if hw_summary else _("Generic"))
        )

        pkgs = results.get('unnecessary_pkgs', [])
        self._packages = pkgs

        if not pkgs:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=_("No unnecessary drivers found"))
            label.set_margin_top(20)
            label.set_margin_bottom(20)
            row.add(label)
            self.list_box.add(row)
        else:
            for pkg in pkgs:
                # pkg puede ser dict o namedtuple
                if isinstance(pkg, dict):
                    pkg_name    = pkg.get('name', '')
                    pkg_vendor  = pkg.get('vendor', '')
                    pkg_size    = pkg.get('installed_size', 0)
                else:
                    pkg_name   = pkg.name
                    pkg_vendor = pkg.vendor
                    pkg_size   = pkg.installed_size

                row = Gtk.ListBoxRow()
                row_box = Gtk.Box(spacing=12)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)
                row_box.set_margin_top(8)
                row_box.set_margin_bottom(8)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_check_toggled)
                self._checkboxes[pkg_name] = check
                row_box.pack_start(check, False, False, 0)

                name_label = Gtk.Label(label=pkg_name)
                name_label.set_halign(Gtk.Align.START)
                row_box.pack_start(name_label, True, True, 0)

                vendor_label = Gtk.Label(label=f"[{pkg_vendor}]")
                vendor_label.get_style_context().add_class('dim-label')
                row_box.pack_start(vendor_label, False, False, 0)

                size_label = Gtk.Label(label=_fmt_size(pkg_size * 1024))
                size_label.get_style_context().add_class('dim-label')
                size_label.set_width_chars(8)
                size_label.set_halign(Gtk.Align.END)
                row_box.pack_end(size_label, False, False, 0)

                row.add(row_box)
                self.list_box.add(row)

        self.list_box.show_all()

    def _on_select_all(self, btn):
        active = btn.get_active()
        for check in self._checkboxes.values():
            check.set_active(active)

    def _on_check_toggled(self, check):
        any_selected = any(c.get_active() for c in self._checkboxes.values())
        self.remove_btn.set_sensitive(any_selected)

    def _on_remove_clicked(self, btn):
        selected = [name for name, check in self._checkboxes.items() if check.get_active()]
        if not selected:
            return

        # Confirm dialog
        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected packages?")
        )
        dialog.format_secondary_text(
            _("{} package(s) will be removed and the initramfs will be regenerated.").format(len(selected))
        )
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        self.remove_btn.set_sensitive(False)
        self.parent.set_ui_state(_("Removing drivers and regenerating initramfs..."), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _("Tasks completed successfully.") if success else f"Error: {result.get('stderr', '')}"
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(2, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'apt_purge', 'packages': selected, 'rebuild_initrd': True}, on_done)

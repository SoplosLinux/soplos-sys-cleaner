"""
Firmware tab: shows firmware families in /lib/firmware.
Network families are shown but locked (protected by soplos.conf).
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class FirmwareTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        # Warning banner
        warning_box = Gtk.Box(spacing=8)
        warning_box.set_margin_start(12)
        warning_box.set_margin_end(12)
        warning_box.set_margin_top(10)
        warning_icon = Gtk.Image.new_from_icon_name('dialog-information', Gtk.IconSize.BUTTON)
        warning_box.pack_start(warning_icon, False, False, 0)
        warning_label = Gtk.Label()
        warning_label.set_markup(
            f"<small><i>{_('Firmwares required by detected hardware are locked automatically — only unrecognised firmwares can be removed')}</i></small>"
        )
        warning_label.set_halign(Gtk.Align.START)
        warning_label.set_line_wrap(True)
        warning_box.pack_start(warning_label, True, True, 0)
        self.pack_start(warning_box, False, False, 0)

        # Toolbar
        toolbar = Gtk.Box(spacing=10)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(8)

        self.count_label = Gtk.Label(label="")
        self.count_label.set_halign(Gtk.Align.START)
        toolbar.pack_start(self.count_label, True, True, 0)

        self.select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.select_all_btn.connect('toggled', self._on_select_all)
        toolbar.pack_end(self.select_all_btn, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        # Firmware list in card
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

        # Actions
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(10)
        actions.set_margin_bottom(12)

        self.remove_btn = Gtk.Button()
        btn_box = Gtk.Box(spacing=6)
        btn_box.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        btn_box.pack_start(Gtk.Label(label=_("Remove selected firmwares")), False, False, 0)
        self.remove_btn.add(btn_box)
        self.remove_btn.get_style_context().add_class('destructive-action')
        self.remove_btn.connect('clicked', self._on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        actions.pack_start(self.remove_btn, False, False, 0)
        self.pack_start(actions, False, False, 0)

        self.show_all()

    def populate(self, results: dict):
        for row in self.list_box.get_children():
            self.list_box.remove(row)
        self._checkboxes.clear()

        families = results.get('firmware_families', [])
        is_protected = results.get('is_firmware_protected', lambda x: False)
        sizes = results.get('firmware_sizes', {})

        self.count_label.set_text(
            _("{} firmware families detected").format(len(families))
        )

        for family in families:
            protected = is_protected(family)
            size_kb = sizes.get(family, 0)

            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(spacing=12)
            row_box.set_margin_start(12)
            row_box.set_margin_end(12)
            row_box.set_margin_top(6)
            row_box.set_margin_bottom(6)

            if protected:
                check = Gtk.CheckButton()
                check.set_active(False)
                check.set_sensitive(False)
                check.set_tooltip_text(
                    _("Protected: required by hardware detected on this system")
                )
            else:
                check = Gtk.CheckButton()
                check.connect('toggled', self._on_check_toggled)
                self._checkboxes[family] = check

            row_box.pack_start(check, False, False, 0)

            name_label = Gtk.Label(label=family)
            name_label.set_halign(Gtk.Align.START)
            if protected:
                name_label.get_style_context().add_class('item-protected')
            row_box.pack_start(name_label, True, True, 0)

            if protected:
                lock_icon = Gtk.Image.new_from_icon_name('changes-prevent', Gtk.IconSize.MENU)
                lock_icon.set_tooltip_text(_("Protected: hardware present in this system"))
                row_box.pack_end(lock_icon, False, False, 0)

            size_label = Gtk.Label(label=_fmt_size(size_kb * 1024))
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

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected firmwares?")
        )
        dialog.format_secondary_text(
            _("{} firmware family(s) will be removed from /lib/firmware/\n"
              "The initramfs will be regenerated automatically.").format(len(selected))
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_btn.set_sensitive(False)

        self.parent.set_ui_state(_("Removing firmwares and regenerating initramfs..."), pulse=True)
        
        def _on_done(result):
            success = result.get('success', False)
            msg = _("Firmware removed and initramfs regenerated.") if success else result.get('error', _("Unknown error"))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(2, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'remove_firmware', 'families': selected}, _on_done)

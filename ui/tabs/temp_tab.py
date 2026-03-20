"""
Temp files tab: /tmp and /var/tmp with age filter.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class TempTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._entries = []
        self._checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        # Toolbar with age filter
        toolbar = Gtk.Box(spacing=10)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)

        self.info_label = Gtk.Label(label="")
        self.info_label.set_halign(Gtk.Align.START)
        toolbar.pack_start(self.info_label, True, True, 0)

        filter_label = Gtk.Label(label=_("Keep files from the last:"))
        toolbar.pack_start(filter_label, False, False, 0)

        self.age_combo = Gtk.ComboBoxText()
        for text in [_("1 day"), _("7 days"), _("30 days"), _("DO NOT KEEP (Delete all)")]:
            self.age_combo.append_text(text)
        self.age_combo.set_active(1)  # Default 7 days
        self.age_combo.connect('changed', self._on_filter_changed)
        toolbar.pack_start(self.age_combo, False, False, 0)

        self.select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.select_all_btn.connect('toggled', self._on_select_all)
        toolbar.pack_end(self.select_all_btn, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        # List in card
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
        btn_box.pack_start(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON), False, False, 0)
        btn_box.pack_start(Gtk.Label(label=_("Remove Selected")), False, False, 0)
        self.remove_btn.add(btn_box)
        self.remove_btn.get_style_context().add_class('destructive-action')
        self.remove_btn.connect('clicked', self._on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        actions.pack_start(self.remove_btn, False, False, 0)
        self.pack_start(actions, False, False, 0)
        self.show_all()

    def _get_min_age(self) -> float:
        idx = self.age_combo.get_active()
        if idx < 0:
            return 7.0
        return [1.0, 7.0, 30.0, 0.0][idx]

    def _on_filter_changed(self, combo):
        if self._entries and self.age_combo.get_active() >= 0:
            GLib.idle_add(self._repopulate)

    def _repopulate(self):
        from scanner.temp_files import get_temp_entries
        min_age = self._get_min_age()
        filtered = [e for e in self._entries if e.age_days >= min_age]
        self._fill_list(filtered)

    def populate(self, results: dict):
        self._entries = results.get('temp_entries', [])
        self._repopulate()

    def _fill_list(self, entries):
        for row in self.list_box.get_children():
            row.destroy()
        self._checkboxes.clear()

        total_size = sum(e.size_bytes for e in entries)
        self.info_label.set_text(
            _("{} item(s) — {}").format(len(entries), _fmt_size(total_size))
        )

        if not entries:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=_("No temporary files matching this filter"))
            label.set_margin_top(20)
            label.set_margin_bottom(20)
            row.add(label)
            self.list_box.add(row)
        else:
            for entry in entries:
                row = Gtk.ListBoxRow()
                row_box = Gtk.Box(spacing=12)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)
                row_box.set_margin_top(6)
                row_box.set_margin_bottom(6)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_check_toggled)
                self._checkboxes[entry.path] = check
                row_box.pack_start(check, False, False, 0)

                icon_name = 'folder' if entry.is_dir else 'text-x-generic'
                icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
                row_box.pack_start(icon, False, False, 0)

                path_label = Gtk.Label(label=entry.path)
                path_label.set_halign(Gtk.Align.START)
                path_label.set_ellipsize(3)  # END
                row_box.pack_start(path_label, True, True, 0)

                age_label = Gtk.Label(label=f"{entry.age_days:.0f}d")
                age_label.get_style_context().add_class('dim-label')
                age_label.set_width_chars(5)
                row_box.pack_start(age_label, False, False, 0)

                size_label = Gtk.Label(label=_fmt_size(entry.size_bytes))
                size_label.get_style_context().add_class('dim-label')
                size_label.set_width_chars(9)
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
        selected = [path for path, check in self._checkboxes.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected temporary files?")
        )
        dialog.format_secondary_text(_("{} item(s) to remove.").format(len(selected)))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_btn.set_sensitive(False)

        def do_remove():
            from cleaner.remover import delete_temp_paths
            self.parent.set_ui_state(_("Removing temporary files..."), pulse=True)
            success, msg = delete_temp_paths(selected)
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_remove, daemon=True).start()

"""
Logs tab: /var/log entries and journald cleanup. Root only.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class LogsTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._log_entries = []
        self._checkboxes = {}
        self._journald_size = 0
        self._build_ui()

    def _build_ui(self):
        toolbar = Gtk.Box(spacing=10)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)

        self.info_label = Gtk.Label(label="")
        self.info_label.set_halign(Gtk.Align.START)
        toolbar.pack_start(self.info_label, True, True, 0)

        self.select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.select_all_btn.connect('toggled', self._on_select_all)
        toolbar.pack_end(self.select_all_btn, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        # Journald card
        journald_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        journald_card.get_style_context().add_class('summary-card')
        journald_card.set_margin_start(12)
        journald_card.set_margin_end(12)
        journald_card.set_margin_bottom(8)

        jd_title = Gtk.Label()
        jd_title.set_markup(f"<b>{_('Systemd Journal')}</b>")
        jd_title.set_halign(Gtk.Align.START)
        journald_card.pack_start(jd_title, False, False, 0)

        self.journald_label = Gtk.Label(label=_("Scanning..."))
        self.journald_label.set_halign(Gtk.Align.START)
        journald_card.pack_start(self.journald_label, False, False, 0)

        jd_btn_box = Gtk.Box(spacing=10)
        self.vacuum_size_btn = Gtk.Button(label=_("Keep last 100 MB"))
        self.vacuum_size_btn.connect('clicked', lambda b: self._vacuum_journal('--vacuum-size=100M'))
        self.vacuum_time_btn = Gtk.Button(label=_("Keep last 2 weeks"))
        self.vacuum_time_btn.connect('clicked', lambda b: self._vacuum_journal('--vacuum-time=2weeks'))
        jd_btn_box.pack_start(self.vacuum_size_btn, False, False, 0)
        jd_btn_box.pack_start(self.vacuum_time_btn, False, False, 0)
        journald_card.pack_start(jd_btn_box, False, False, 0)
        self.pack_start(journald_card, False, False, 0)

        # /var/log list card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class('summary-card')
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(8)

        log_title = Gtk.Label()
        log_title.set_markup(f"<b>{_('/var/log entries')}</b>")
        log_title.set_halign(Gtk.Align.START)
        log_title.set_margin_start(8)
        log_title.set_margin_top(8)
        card.pack_start(log_title, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        card.pack_start(scroll, True, True, 0)
        self.pack_start(card, True, True, 0)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self.list_box)

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

    def populate(self, results: dict):
        from scanner.logs import LogEntry
        raw = results.get('log_entries', [])
        # Accept both LogEntry namedtuples and dicts (from root scan JSON)
        self._log_entries = [
            e if hasattr(e, 'path') else LogEntry(name=e['name'], path=e['path'], size_bytes=e['size_bytes'])
            for e in raw
        ]
        journald = results.get('journald', {})
        self._journald_size = journald.get('size_bytes', 0) if isinstance(journald, dict) else journald.size_bytes
        disk_str = journald.get('disk_usage_str', '') if isinstance(journald, dict) else journald.disk_usage_str
        self.journald_label.set_text(disk_str or _("{} used by journal").format(_fmt_size(self._journald_size)))
        self._fill_list()

    def _fill_list(self):
        for row in self.list_box.get_children():
            row.destroy()
        self._checkboxes.clear()

        total = sum(e.size_bytes for e in self._log_entries)
        self.info_label.set_text(
            _("{} item(s) — {}").format(len(self._log_entries), _fmt_size(total))
        )

        if not self._log_entries:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=_("No log files found"))
            lbl.set_margin_top(20)
            lbl.set_margin_bottom(20)
            row.add(lbl)
            self.list_box.add(row)
        else:
            for entry in self._log_entries:
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

                import os
                icon_name = 'folder' if os.path.isdir(entry.path) else 'text-x-script'
                row_box.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU), False, False, 0)

                lbl = Gtk.Label(label=entry.name)
                lbl.set_halign(Gtk.Align.START)
                lbl.set_ellipsize(3)
                row_box.pack_start(lbl, True, True, 0)

                size_lbl = Gtk.Label(label=_fmt_size(entry.size_bytes))
                size_lbl.get_style_context().add_class('dim-label')
                size_lbl.set_width_chars(9)
                size_lbl.set_halign(Gtk.Align.END)
                row_box.pack_end(size_lbl, False, False, 0)

                row.add(row_box)
                self.list_box.add(row)

        self.list_box.show_all()

    def _on_select_all(self, btn):
        for check in self._checkboxes.values():
            check.set_active(btn.get_active())

    def _on_check_toggled(self, check):
        self.remove_btn.set_sensitive(any(c.get_active() for c in self._checkboxes.values()))

    def _vacuum_journal(self, flag: str):
        self.parent.set_ui_state(_("Cleaning journal..."), pulse=True)
        def _on_done(result):
            success = result.get('success', False)
            msg = _("Journal cleaned.") if success else result.get('error', _("Unknown error"))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))
            
        self.parent.run_root_action({'action': 'vacuum_journal', 'flag': flag}, _on_done)

    def _on_remove_clicked(self, btn):
        selected = [path for path, check in self._checkboxes.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected log entries?")
        )
        dialog.format_secondary_text(_("{} item(s) will be permanently deleted.").format(len(selected)))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        self.parent.set_ui_state(_("Removing log files..."), pulse=True)
        def _on_done(result):
            success = result.get('success', False)
            msg = _("{} item(s) removed.").format(len(selected)) if success else result.get('error', _("Unknown error"))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'delete_paths', 'paths': selected}, _on_done)

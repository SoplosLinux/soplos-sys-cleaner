"""
Installed Apps tab: lists manually installed packages with search and uninstall.
Scanning is user-level; uninstall uses pkexec.
"""

import shutil
import subprocess
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class InstalledAppsTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._all_apps = []
        self._checkboxes = {}   # name -> CheckButton
        self._pending_results = None
        self._build_ui()
        self.connect('map', self._on_mapped)

    def _build_ui(self):
        # Toolbar: count + search + select all
        toolbar = Gtk.Box(spacing=10)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)

        self.info_label = Gtk.Label(label="")
        self.info_label.set_halign(Gtk.Align.START)
        toolbar.pack_start(self.info_label, False, False, 0)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search packages…"))
        self.search_entry.connect('search-changed', self._on_search_changed)
        toolbar.pack_start(self.search_entry, True, True, 0)

        self.select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.select_all_btn.connect('toggled', self._on_select_all)
        toolbar.pack_end(self.select_all_btn, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        # App list in card
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
        self.list_box.set_filter_func(self._filter_row)
        scroll.add(self.list_box)

        # Actions
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(10)
        actions.set_margin_bottom(12)

        self.remove_btn = Gtk.Button()
        btn_box = Gtk.Box(spacing=6)
        btn_box.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        btn_box.pack_start(Gtk.Label(label=_("Uninstall Selected")), False, False, 0)
        self.remove_btn.add(btn_box)
        self.remove_btn.get_style_context().add_class('destructive-action')
        self.remove_btn.connect('clicked', self._on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        actions.pack_start(self.remove_btn, False, False, 0)
        self.pack_start(actions, False, False, 0)

        self.show_all()

    def populate(self, results: dict):
        if self.get_mapped():
            self._do_populate(results)
        else:
            self._pending_results = results

    def _on_mapped(self, widget):
        if self._pending_results is not None:
            results = self._pending_results
            self._pending_results = None
            self._do_populate(results)

    def _do_populate(self, results: dict):
        self._all_apps = results.get('installed_apps', [])
        self._fill_list()

    def _fill_list(self):
        for row in self.list_box.get_children():
            self.list_box.remove(row)
        self._checkboxes.clear()
        self.select_all_btn.set_active(False)

        total_size = sum(a.size_kb for a in self._all_apps) * 1024
        self.info_label.set_text(
            _("{} package(s) — {}").format(len(self._all_apps), _fmt_size(total_size))
        )

        if not self._all_apps:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=_("No manually installed packages found"))
            lbl.set_margin_top(20)
            lbl.set_margin_bottom(20)
            row.add(lbl)
            self.list_box.add(row)
        else:
            for app in self._all_apps:
                row = Gtk.ListBoxRow()
                row.app_name = app.name  # used by filter

                row_box = Gtk.Box(spacing=12)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)
                row_box.set_margin_top(5)
                row_box.set_margin_bottom(5)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_check_toggled)
                self._checkboxes[app.name] = check
                row_box.pack_start(check, False, False, 0)

                icon_name = 'application-x-executable' if app.has_desktop else 'package-x-generic'
                row_box.pack_start(
                    Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU), False, False, 0
                )

                name_lbl = Gtk.Label(label=app.name)
                name_lbl.set_halign(Gtk.Align.START)
                row_box.pack_start(name_lbl, False, False, 0)

                if app.summary:
                    summary_lbl = Gtk.Label(label=app.summary)
                    summary_lbl.get_style_context().add_class('dim-label')
                    summary_lbl.set_halign(Gtk.Align.START)
                    summary_lbl.set_ellipsize(3)
                    row_box.pack_start(summary_lbl, True, True, 0)
                else:
                    row_box.pack_start(Gtk.Box(), True, True, 0)

                size_lbl = Gtk.Label(label=_fmt_size(app.size_kb * 1024))
                size_lbl.get_style_context().add_class('dim-label')
                size_lbl.set_width_chars(9)
                size_lbl.set_halign(Gtk.Align.END)
                row_box.pack_end(size_lbl, False, False, 0)

                row.add(row_box)
                self.list_box.add(row)

        self.list_box.show_all()

    def _filter_row(self, row):
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        return query in getattr(row, 'app_name', '').lower()

    def _on_search_changed(self, entry):
        self.list_box.invalidate_filter()

    def _on_select_all(self, btn):
        active = btn.get_active()
        for name, check in self._checkboxes.items():
            row = check.get_parent().get_parent()
            if self._filter_row(row):
                check.set_active(active)

    def _on_check_toggled(self, check):
        self.remove_btn.set_sensitive(any(c.get_active() for c in self._checkboxes.values()))

    def _on_remove_clicked(self, btn):
        selected = [name for name, check in self._checkboxes.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Uninstall selected packages?")
        )
        dialog.format_secondary_text(
            _("{} package(s) will be removed:\n{}").format(
                len(selected), ', '.join(selected[:10]) + ('…' if len(selected) > 10 else '')
            )
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        def do_remove():
            self.parent.set_ui_state(_("Uninstalling packages..."), pulse=True)
            try:
                pkexec = shutil.which('pkexec') or 'pkexec'
                result = subprocess.run(
                    [pkexec, 'apt-get', 'remove', '-y'] + selected,
                    capture_output=True, text=True
                )
                success = result.returncode == 0
                msg = _("Packages uninstalled successfully.") if success else result.stderr.strip()
            except Exception as e:
                success, msg = False, str(e)
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_user_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_remove, daemon=True).start()

"""
Flatpak tab: manage installed Flatpak apps and remove unused runtimes.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class FlatpakTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._apps = []
        self._entries = []
        self._app_checkboxes = {}
        self._runtime_checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        # ── Section 1: Installed Apps ──
        apps_header = Gtk.Box(spacing=10)
        apps_header.set_margin_start(12)
        apps_header.set_margin_end(12)
        apps_header.set_margin_top(12)
        apps_header.set_margin_bottom(6)

        self.apps_info_label = Gtk.Label(label="")
        self.apps_info_label.set_halign(Gtk.Align.START)
        apps_header.pack_start(self.apps_info_label, True, True, 0)

        self.apps_select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.apps_select_all_btn.connect('toggled', self._on_apps_select_all)
        apps_header.pack_end(self.apps_select_all_btn, False, False, 0)
        self.pack_start(apps_header, False, False, 0)

        apps_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        apps_card.get_style_context().add_class('summary-card')
        apps_card.set_margin_start(12)
        apps_card.set_margin_end(12)
        apps_card.set_margin_bottom(4)
        apps_scroll = Gtk.ScrolledWindow()
        apps_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        apps_scroll.set_min_content_height(120)
        apps_card.pack_start(apps_scroll, True, True, 0)
        self.pack_start(apps_card, True, True, 0)

        self.apps_list_box = Gtk.ListBox()
        self.apps_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        apps_scroll.add(self.apps_list_box)

        self.uninstall_btn = Gtk.Button()
        ubtn_box = Gtk.Box(spacing=6)
        ubtn_box.pack_start(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON), False, False, 0)
        ubtn_box.pack_start(Gtk.Label(label=_("Uninstall Selected")), False, False, 0)
        self.uninstall_btn.add(ubtn_box)
        self.uninstall_btn.get_style_context().add_class('destructive-action')
        self.uninstall_btn.connect('clicked', self._on_uninstall_clicked)
        self.uninstall_btn.set_sensitive(False)
        uninstall_box = Gtk.Box()
        uninstall_box.set_halign(Gtk.Align.CENTER)
        uninstall_box.set_margin_top(6)
        uninstall_box.set_margin_bottom(6)
        uninstall_box.pack_start(self.uninstall_btn, False, False, 0)
        self.pack_start(uninstall_box, False, False, 0)

        # ── Separator ──
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_start(12)
        sep.set_margin_end(12)
        sep.set_margin_top(2)
        sep.set_margin_bottom(2)
        self.pack_start(sep, False, False, 0)

        # ── Section 2: Unused Runtimes ──
        runtimes_header = Gtk.Box(spacing=10)
        runtimes_header.set_margin_start(12)
        runtimes_header.set_margin_end(12)
        runtimes_header.set_margin_top(6)
        runtimes_header.set_margin_bottom(6)

        self.runtimes_info_label = Gtk.Label(label="")
        self.runtimes_info_label.set_halign(Gtk.Align.START)
        runtimes_header.pack_start(self.runtimes_info_label, True, True, 0)

        self.runtimes_select_all_btn = Gtk.CheckButton(label=_("Select all"))
        self.runtimes_select_all_btn.connect('toggled', self._on_runtimes_select_all)
        runtimes_header.pack_end(self.runtimes_select_all_btn, False, False, 0)
        self.pack_start(runtimes_header, False, False, 0)

        runtimes_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        runtimes_card.get_style_context().add_class('summary-card')
        runtimes_card.set_margin_start(12)
        runtimes_card.set_margin_end(12)
        runtimes_card.set_margin_bottom(4)
        runtimes_scroll = Gtk.ScrolledWindow()
        runtimes_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        runtimes_scroll.set_min_content_height(80)
        runtimes_card.pack_start(runtimes_scroll, True, True, 0)
        self.pack_start(runtimes_card, True, True, 0)

        self.runtimes_list_box = Gtk.ListBox()
        self.runtimes_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        runtimes_scroll.add(self.runtimes_list_box)

        self.remove_btn = Gtk.Button()
        rbtn_box = Gtk.Box(spacing=6)
        rbtn_box.pack_start(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON), False, False, 0)
        rbtn_box.pack_start(Gtk.Label(label=_("Remove Selected")), False, False, 0)
        self.remove_btn.add(rbtn_box)
        self.remove_btn.get_style_context().add_class('destructive-action')
        self.remove_btn.connect('clicked', self._on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        remove_box = Gtk.Box()
        remove_box.set_halign(Gtk.Align.CENTER)
        remove_box.set_margin_top(6)
        remove_box.set_margin_bottom(10)
        remove_box.pack_start(self.remove_btn, False, False, 0)
        self.pack_start(remove_box, False, False, 0)

        self.show_all()

    def populate(self, results: dict):
        self._apps = results.get('flatpak_apps', [])
        self._entries = results.get('flatpak_entries', [])
        self._fill_apps_list()
        self._fill_runtimes_list()

    def _fill_apps_list(self):
        for row in self.apps_list_box.get_children():
            row.destroy()
        self._app_checkboxes.clear()

        if not self._apps:
            from scanner.flatpak import flatpak_available
            if not flatpak_available():
                msg = _("Flatpak is not installed on this system")
            else:
                msg = _("No Flatpak apps installed")
            self.apps_info_label.set_text(msg)
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=msg)
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            row.add(lbl)
            self.apps_list_box.add(row)
        else:
            total = sum(a.size_bytes for a in self._apps)
            self.apps_info_label.set_text(
                _("{} app(s) installed — {}").format(len(self._apps), _fmt_size(total))
            )
            for app in self._apps:
                row = Gtk.ListBoxRow()
                row_box = Gtk.Box(spacing=12)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)
                row_box.set_margin_top(6)
                row_box.set_margin_bottom(6)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_app_check_toggled)
                self._app_checkboxes[app.app_id] = check
                row_box.pack_start(check, False, False, 0)

                row_box.pack_start(
                    Gtk.Image.new_from_icon_name('package-x-generic', Gtk.IconSize.MENU),
                    False, False, 0
                )

                name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                name_lbl = Gtk.Label(label=app.name)
                name_lbl.set_halign(Gtk.Align.START)
                name_lbl.set_ellipsize(3)
                name_box.pack_start(name_lbl, False, False, 0)
                id_lbl = Gtk.Label(label=app.app_id)
                id_lbl.set_halign(Gtk.Align.START)
                id_lbl.set_ellipsize(3)
                id_lbl.get_style_context().add_class('dim-label')
                name_box.pack_start(id_lbl, False, False, 0)
                row_box.pack_start(name_box, True, True, 0)

                if app.version:
                    ver_lbl = Gtk.Label(label=app.version)
                    ver_lbl.get_style_context().add_class('dim-label')
                    ver_lbl.set_width_chars(10)
                    ver_lbl.set_halign(Gtk.Align.END)
                    row_box.pack_end(ver_lbl, False, False, 0)

                size_lbl = Gtk.Label(label=_fmt_size(app.size_bytes))
                size_lbl.get_style_context().add_class('dim-label')
                size_lbl.set_width_chars(9)
                size_lbl.set_halign(Gtk.Align.END)
                row_box.pack_end(size_lbl, False, False, 0)

                row.add(row_box)
                self.apps_list_box.add(row)

        self.apps_list_box.show_all()

    def _fill_runtimes_list(self):
        for row in self.runtimes_list_box.get_children():
            row.destroy()
        self._runtime_checkboxes.clear()

        if not self._entries:
            self.runtimes_info_label.set_text(_("Unused runtimes"))
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=_("No unused Flatpak runtimes found"))
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            row.add(lbl)
            self.runtimes_list_box.add(row)
        else:
            total = sum(e.size_bytes for e in self._entries)
            self.runtimes_info_label.set_text(
                _("{} unused runtime(s) — {}").format(len(self._entries), _fmt_size(total))
            )
            for entry in self._entries:
                row = Gtk.ListBoxRow()
                row_box = Gtk.Box(spacing=12)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)
                row_box.set_margin_top(6)
                row_box.set_margin_bottom(6)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_runtime_check_toggled)
                self._runtime_checkboxes[entry.ref] = check
                row_box.pack_start(check, False, False, 0)

                row_box.pack_start(
                    Gtk.Image.new_from_icon_name('package-x-generic', Gtk.IconSize.MENU),
                    False, False, 0
                )

                lbl = Gtk.Label(label=entry.ref)
                lbl.set_halign(Gtk.Align.START)
                lbl.set_ellipsize(3)
                row_box.pack_start(lbl, True, True, 0)

                size_lbl = Gtk.Label(label=_fmt_size(entry.size_bytes))
                size_lbl.get_style_context().add_class('dim-label')
                size_lbl.set_width_chars(9)
                size_lbl.set_halign(Gtk.Align.END)
                row_box.pack_end(size_lbl, False, False, 0)

                row.add(row_box)
                self.runtimes_list_box.add(row)

        self.runtimes_list_box.show_all()

    def _on_apps_select_all(self, btn):
        for check in self._app_checkboxes.values():
            check.set_active(btn.get_active())

    def _on_runtimes_select_all(self, btn):
        for check in self._runtime_checkboxes.values():
            check.set_active(btn.get_active())

    def _on_app_check_toggled(self, check):
        self.uninstall_btn.set_sensitive(
            any(c.get_active() for c in self._app_checkboxes.values())
        )

    def _on_runtime_check_toggled(self, check):
        self.remove_btn.set_sensitive(
            any(c.get_active() for c in self._runtime_checkboxes.values())
        )

    def _on_uninstall_clicked(self, btn):
        selected = [app_id for app_id, check in self._app_checkboxes.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Uninstall selected Flatpak apps?")
        )
        dialog.format_secondary_text(_("{} app(s) will be uninstalled.").format(len(selected)))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        def do_uninstall():
            import subprocess
            self.parent.set_ui_state(_("Uninstalling Flatpak apps..."), pulse=True)
            try:
                result = subprocess.run(
                    ['flatpak', 'uninstall', '-y'] + selected,
                    capture_output=True, text=True
                )
                success = result.returncode == 0
                msg = _("Flatpak apps uninstalled.") if success else f"Error: {result.stderr.strip()}"
            except Exception as e:
                success, msg = False, str(e)
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            def _reset_apps_select_all():
                self.apps_select_all_btn.handler_block_by_func(self._on_apps_select_all)
                self.apps_select_all_btn.set_active(False)
                self.apps_select_all_btn.handler_unblock_by_func(self._on_apps_select_all)
            GLib.idle_add(_reset_apps_select_all)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_user_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_uninstall, daemon=True).start()

    def _on_remove_clicked(self, btn):
        selected = [ref for ref, check in self._runtime_checkboxes.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected Flatpak runtimes?")
        )
        dialog.format_secondary_text(_("{} runtime(s) will be uninstalled.").format(len(selected)))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        def do_remove():
            import subprocess
            self.parent.set_ui_state(_("Removing Flatpak runtimes..."), pulse=True)
            try:
                result = subprocess.run(
                    ['flatpak', 'uninstall', '-y'] + selected,
                    capture_output=True, text=True
                )
                success = result.returncode == 0
                msg = _("Flatpak runtimes removed.") if success else f"Error: {result.stderr.strip()}"
            except Exception as e:
                success, msg = False, str(e)
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            def _reset_runtimes_select_all():
                self.runtimes_select_all_btn.handler_block_by_func(self._on_runtimes_select_all)
                self.runtimes_select_all_btn.set_active(False)
                self.runtimes_select_all_btn.handler_unblock_by_func(self._on_runtimes_select_all)
            GLib.idle_add(_reset_runtimes_select_all)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_user_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_remove, daemon=True).start()

"""
Snap tab: uninstall installed snaps and remove old/disabled revisions.
"""

import subprocess
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class SnapTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._app_checks = {}       # name -> CheckButton
        self._revision_checks = {}  # "name:rev" -> CheckButton
        self._build_ui()

    def _build_ui(self):
        # ── Section 1: Installed snaps ────────────────────────────────────────
        apps_header = Gtk.Box(spacing=10)
        apps_header.set_margin_start(12)
        apps_header.set_margin_end(12)
        apps_header.set_margin_top(12)
        apps_header.set_margin_bottom(6)

        self.apps_info_label = Gtk.Label(label='')
        self.apps_info_label.set_halign(Gtk.Align.START)
        apps_header.pack_start(self.apps_info_label, True, True, 0)

        self.apps_select_all = Gtk.CheckButton(label=_("Select all"))
        self.apps_select_all.connect('toggled', self._on_apps_select_all)
        apps_header.pack_end(self.apps_select_all, False, False, 0)
        self.pack_start(apps_header, False, False, 0)

        apps_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        apps_card.get_style_context().add_class('summary-card')
        apps_card.set_margin_start(12)
        apps_card.set_margin_end(12)
        apps_card.set_margin_bottom(6)
        apps_scroll = Gtk.ScrolledWindow()
        apps_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        apps_scroll.set_min_content_height(80)
        apps_scroll.set_max_content_height(200)
        apps_card.pack_start(apps_scroll, True, True, 0)
        self.pack_start(apps_card, False, False, 0)

        self.apps_list = Gtk.ListBox()
        self.apps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        apps_scroll.add(self.apps_list)

        apps_actions = Gtk.Box(spacing=12)
        apps_actions.set_halign(Gtk.Align.CENTER)
        apps_actions.set_margin_top(4)
        apps_actions.set_margin_bottom(8)

        self.uninstall_btn = Gtk.Button()
        _b1 = Gtk.Box(spacing=6)
        _b1.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        _b1.pack_start(Gtk.Label(label=_("Uninstall Selected")), False, False, 0)
        self.uninstall_btn.add(_b1)
        self.uninstall_btn.get_style_context().add_class('destructive-action')
        self.uninstall_btn.connect('clicked', self._on_uninstall_clicked)
        self.uninstall_btn.set_sensitive(False)
        apps_actions.pack_start(self.uninstall_btn, False, False, 0)
        self.pack_start(apps_actions, False, False, 0)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_start(12)
        sep.set_margin_end(12)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        self.pack_start(sep, False, False, 0)

        # ── Section 2: Old revisions ──────────────────────────────────────────
        rev_header = Gtk.Box(spacing=10)
        rev_header.set_margin_start(12)
        rev_header.set_margin_end(12)
        rev_header.set_margin_top(6)
        rev_header.set_margin_bottom(6)

        self.rev_info_label = Gtk.Label(label='')
        self.rev_info_label.set_halign(Gtk.Align.START)
        rev_header.pack_start(self.rev_info_label, True, True, 0)

        self.rev_select_all = Gtk.CheckButton(label=_("Select all"))
        self.rev_select_all.connect('toggled', self._on_rev_select_all)
        rev_header.pack_end(self.rev_select_all, False, False, 0)
        self.pack_start(rev_header, False, False, 0)

        rev_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        rev_card.get_style_context().add_class('summary-card')
        rev_card.set_margin_start(12)
        rev_card.set_margin_end(12)
        rev_card.set_margin_bottom(6)
        rev_scroll = Gtk.ScrolledWindow()
        rev_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rev_scroll.set_min_content_height(60)
        rev_scroll.set_max_content_height(160)
        rev_card.pack_start(rev_scroll, True, True, 0)
        self.pack_start(rev_card, False, False, 0)

        self.rev_list = Gtk.ListBox()
        self.rev_list.set_selection_mode(Gtk.SelectionMode.NONE)
        rev_scroll.add(self.rev_list)

        rev_actions = Gtk.Box(spacing=12)
        rev_actions.set_halign(Gtk.Align.CENTER)
        rev_actions.set_margin_top(4)
        rev_actions.set_margin_bottom(10)

        self.remove_rev_btn = Gtk.Button()
        _b2 = Gtk.Box(spacing=6)
        _b2.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        _b2.pack_start(Gtk.Label(label=_("Remove Selected Revisions")), False, False, 0)
        self.remove_rev_btn.add(_b2)
        self.remove_rev_btn.get_style_context().add_class('destructive-action')
        self.remove_rev_btn.connect('clicked', self._on_remove_rev_clicked)
        self.remove_rev_btn.set_sensitive(False)
        rev_actions.pack_start(self.remove_rev_btn, False, False, 0)
        self.pack_start(rev_actions, False, False, 0)

        self.show_all()

    # ── populate ──────────────────────────────────────────────────────────────

    def populate(self, results: dict):
        self._populate_apps(results.get('snap_apps', []))
        self._populate_revisions(results.get('snap_revisions', []))

    def _populate_apps(self, apps: list):
        for row in self.apps_list.get_children():
            self.apps_list.remove(row)
        self._app_checks.clear()

        if not apps:
            from scanner.snap import is_snap_available
            msg = _("Snap is not installed") if not is_snap_available() else _("No snaps installed")
            self.apps_info_label.set_text(msg)
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=msg)
            lbl.set_margin_top(16)
            lbl.set_margin_bottom(16)
            row.add(lbl)
            self.apps_list.add(row)
        else:
            total = sum(a['size_bytes'] for a in apps)
            self.apps_info_label.set_text(
                _("{} snap(s) installed — {}").format(len(apps), _fmt_size(total))
            )
            for app in apps:
                row = Gtk.ListBoxRow()
                box = Gtk.Box(spacing=12)
                box.set_margin_start(12)
                box.set_margin_end(12)
                box.set_margin_top(6)
                box.set_margin_bottom(6)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_app_check_toggled)
                self._app_checks[app['name']] = check
                box.pack_start(check, False, False, 0)
                box.pack_start(
                    Gtk.Image.new_from_icon_name('package-x-generic', Gtk.IconSize.MENU),
                    False, False, 0
                )

                name_lbl = Gtk.Label(label=app['name'])
                name_lbl.set_halign(Gtk.Align.START)
                box.pack_start(name_lbl, True, True, 0)

                ch_lbl = Gtk.Label(label=app.get('channel', ''))
                ch_lbl.get_style_context().add_class('dim-label')
                box.pack_start(ch_lbl, False, False, 0)

                ver_lbl = Gtk.Label(label=app.get('version', ''))
                ver_lbl.get_style_context().add_class('dim-label')
                box.pack_start(ver_lbl, False, False, 0)

                size_lbl = Gtk.Label(label=_fmt_size(app['size_bytes']))
                size_lbl.get_style_context().add_class('dim-label')
                size_lbl.set_width_chars(9)
                size_lbl.set_halign(Gtk.Align.END)
                box.pack_end(size_lbl, False, False, 0)

                row.add(box)
                self.apps_list.add(row)

        self.apps_list.show_all()

    def _populate_revisions(self, revisions: list):
        for row in self.rev_list.get_children():
            self.rev_list.remove(row)
        self._revision_checks.clear()

        if not revisions:
            self.rev_info_label.set_text(_("No old Snap revisions found"))
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=_("No old Snap revisions found"))
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            row.add(lbl)
            self.rev_list.add(row)
        else:
            total = sum(r['size_bytes'] for r in revisions)
            self.rev_info_label.set_text(
                _("{} old revision(s) — {}").format(len(revisions), _fmt_size(total))
            )
            for rev in revisions:
                key = f"{rev['name']}:{rev['revision']}"
                row = Gtk.ListBoxRow()
                box = Gtk.Box(spacing=12)
                box.set_margin_start(12)
                box.set_margin_end(12)
                box.set_margin_top(6)
                box.set_margin_bottom(6)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_rev_check_toggled)
                self._revision_checks[key] = check
                box.pack_start(check, False, False, 0)
                box.pack_start(
                    Gtk.Image.new_from_icon_name('package-x-generic', Gtk.IconSize.MENU),
                    False, False, 0
                )

                name_lbl = Gtk.Label(label=rev['name'])
                name_lbl.set_halign(Gtk.Align.START)
                box.pack_start(name_lbl, True, True, 0)

                rev_lbl = Gtk.Label(label=f"rev. {rev['revision']}")
                rev_lbl.get_style_context().add_class('dim-label')
                box.pack_start(rev_lbl, False, False, 0)

                size_lbl = Gtk.Label(label=_fmt_size(rev['size_bytes']))
                size_lbl.get_style_context().add_class('dim-label')
                size_lbl.set_width_chars(9)
                size_lbl.set_halign(Gtk.Align.END)
                box.pack_end(size_lbl, False, False, 0)

                row.add(box)
                self.rev_list.add(row)

        self.rev_list.show_all()

    # ── select-all helpers ────────────────────────────────────────────────────

    def _on_apps_select_all(self, btn):
        for check in self._app_checks.values():
            check.set_active(btn.get_active())

    def _on_rev_select_all(self, btn):
        for check in self._revision_checks.values():
            check.set_active(btn.get_active())

    def _on_app_check_toggled(self, _):
        self.uninstall_btn.set_sensitive(
            any(c.get_active() for c in self._app_checks.values())
        )

    def _on_rev_check_toggled(self, _):
        self.remove_rev_btn.set_sensitive(
            any(c.get_active() for c in self._revision_checks.values())
        )

    # ── actions ───────────────────────────────────────────────────────────────

    def _on_uninstall_clicked(self, btn):
        selected = [name for name, check in self._app_checks.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Uninstall selected snaps?")
        )
        dialog.format_secondary_text(
            _("{} snap(s) will be fully removed including all their data.").format(len(selected))
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        def do_remove():
            self.parent.set_ui_state(_("Uninstalling snaps..."), pulse=True)
            # Batch all removals in one pkexec call → single password prompt
            cmds = ' && '.join(
                f'snap remove --purge {name}' for name in selected
            )
            result = subprocess.run(
                ['pkexec', 'bash', '-c', cmds],
                capture_output=True, text=True
            )
            success = result.returncode == 0
            msg = _("Snaps uninstalled.") if success else result.stderr.strip()
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_user_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_remove, daemon=True).start()

    def _on_remove_rev_clicked(self, btn):
        selected = [key for key, check in self._revision_checks.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected Snap revisions?")
        )
        dialog.format_secondary_text(
            _("{} old revision(s) will be permanently removed.").format(len(selected))
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        def do_remove():
            self.parent.set_ui_state(_("Removing Snap revisions..."), pulse=True)
            cmds = ' && '.join(
                f'snap remove --revision {key.split(":", 1)[1]} {key.split(":", 1)[0]}'
                for key in selected
            )
            result = subprocess.run(
                ['pkexec', 'bash', '-c', cmds],
                capture_output=True, text=True
            )
            success = result.returncode == 0
            msg = _("Snap revisions removed.") if success else result.stderr.strip()
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_user_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_remove, daemon=True).start()

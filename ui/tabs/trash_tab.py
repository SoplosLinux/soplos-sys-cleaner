"""
Trash tab: empty user trash (~/.local/share/Trash).
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class TrashTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._trash_info = None
        self._build_ui()

    def _build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        outer.set_valign(Gtk.Align.CENTER)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_margin_top(40)

        icon = Gtk.Image.new_from_icon_name('user-trash-full', Gtk.IconSize.DIALOG)
        icon.set_pixel_size(64)
        outer.pack_start(icon, False, False, 0)

        self.info_label = Gtk.Label()
        self.info_label.set_markup(f"<span size='large'>{_('Scanning...')}</span>")
        self.info_label.set_justify(Gtk.Justification.CENTER)
        outer.pack_start(self.info_label, False, False, 0)

        self.empty_btn = Gtk.Button()
        btn_box = Gtk.Box(spacing=6)
        btn_box.pack_start(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON), False, False, 0)
        btn_box.pack_start(Gtk.Label(label=_("Empty Trash")), False, False, 0)
        self.empty_btn.add(btn_box)
        self.empty_btn.get_style_context().add_class('destructive-action')
        self.empty_btn.connect('clicked', self._on_empty_clicked)
        self.empty_btn.set_sensitive(False)
        self.empty_btn.set_halign(Gtk.Align.CENTER)
        outer.pack_start(self.empty_btn, False, False, 0)

        self.pack_start(outer, True, True, 0)
        self.show_all()

    def populate(self, results: dict):
        self._trash_info = results.get('trash_info')
        if self._trash_info:
            if self._trash_info.files_count > 0:
                self.info_label.set_markup(
                    f"<span size='large'><b>{_fmt_size(self._trash_info.size_bytes)}</b> — "
                    f"{self._trash_info.files_count} {_('item(s) in trash')}</span>"
                )
                self.empty_btn.set_sensitive(True)
            else:
                self.info_label.set_markup(
                    f"<span size='large'>{_('Trash is empty')}</span>"
                )
                self.empty_btn.set_sensitive(False)

    def _on_empty_clicked(self, btn):
        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Empty the trash?")
        )
        dialog.format_secondary_text(_("This will permanently delete all items in the trash."))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        btn.set_sensitive(False)

        def do_empty():
            from cleaner.remover import delete_temp_paths
            import os
            self.parent.set_ui_state(_("Emptying trash..."), pulse=True)
            trash_files = os.path.join(os.path.expanduser('~'), '.local', 'share', 'Trash', 'files')
            trash_info = os.path.join(os.path.expanduser('~'), '.local', 'share', 'Trash', 'info')
            paths = []
            for d in (trash_files, trash_info):
                if os.path.isdir(d):
                    try:
                        paths += [os.path.join(d, e) for e in os.listdir(d)]
                    except Exception:
                        pass
            success, msg = delete_temp_paths(paths) if paths else (True, _("Trash already empty."))
            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_user_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_empty, daemon=True).start()

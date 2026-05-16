"""
Kernels tab: list of installed kernels with selective removal.
Active kernel is always protected.
Shows kbuild packages and orphaned /usr/src + /lib/modules directories.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class KernelsTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._kernel_checks  = {}   # version -> {'image', 'headers', 'src', 'kbuild'}
        self._orphan_checks  = {}   # path -> check  (dirs huérfanos)
        self._build_ui()

    def _build_ui(self):
        info_box = Gtk.Box(spacing=10)
        info_box.set_margin_start(12)
        info_box.set_margin_end(12)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(8)

        self.count_label = Gtk.Label(label='')
        self.count_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.count_label, True, True, 0)
        self.pack_start(info_box, False, False, 0)

        # ── Kernels TreeView ──────────────────────────────────────────────────
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class('summary-card')
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        card.pack_start(scroll, True, True, 0)
        self.pack_start(card, True, True, 0)

        # Columns: StatusIcon, Version, Image, Headers, Sources, Kbuild, Size,
        #          activatable flags (img, hdr, src, kbuild), kernel object
        self.store = Gtk.ListStore(
            str,    # 0 icon
            str,    # 1 version
            bool,   # 2 img checked
            bool,   # 3 hdr checked
            bool,   # 4 src checked
            bool,   # 5 kbuild checked
            str,    # 6 size
            bool,   # 7 img activatable
            bool,   # 8 hdr activatable
            bool,   # 9 src activatable
            bool,   # 10 kbuild activatable
            object, # 11 kernel object
        )

        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.set_headers_visible(True)
        self.treeview.get_style_context().add_class('table-view')
        scroll.add(self.treeview)

        renderer_icon = Gtk.CellRendererPixbuf()
        col_status = Gtk.TreeViewColumn('', renderer_icon, icon_name=0)
        self.treeview.append_column(col_status)

        renderer_text = Gtk.CellRendererText()
        col_ver = Gtk.TreeViewColumn(_('Version'), renderer_text, text=1)
        col_ver.set_min_width(180)
        self.treeview.append_column(col_ver)

        for col_idx, act_idx, label in (
            (2, 7,  _('Image')),
            (3, 8,  _('Headers')),
            (4, 9,  _('Sources')),
            (5, 10, _('Kbuild')),
        ):
            r = Gtk.CellRendererToggle()
            r.connect('toggled', self._on_toggled, col_idx)
            col = Gtk.TreeViewColumn(label, r, active=col_idx, activatable=act_idx)
            col.set_alignment(0.5)
            col.set_min_width(90)
            self.treeview.append_column(col)

        renderer_size = Gtk.CellRendererText()
        renderer_size.set_property('xalign', 1.0)
        col_size = Gtk.TreeViewColumn(_('Size'), renderer_size, text=6)
        col_size.set_alignment(1.0)
        col_size.set_min_width(90)
        self.treeview.append_column(col_size)

        # ── Orphaned dirs section ─────────────────────────────────────────────
        self.orphan_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.orphan_card.get_style_context().add_class('summary-card')
        self.orphan_card.set_margin_start(12)
        self.orphan_card.set_margin_end(12)
        self.orphan_card.set_margin_bottom(8)

        orphan_header_box = Gtk.Box(spacing=8)
        orphan_header_box.set_margin_start(12)
        orphan_header_box.set_margin_top(8)
        orphan_header_box.set_margin_bottom(4)
        orphan_icon = Gtk.Image.new_from_icon_name('dialog-warning', Gtk.IconSize.MENU)
        orphan_header_box.pack_start(orphan_icon, False, False, 0)
        self.orphan_title = Gtk.Label()
        self.orphan_title.set_markup(f'<b>{_("Orphaned kernel directories")}</b>')
        self.orphan_title.set_halign(Gtk.Align.START)
        orphan_header_box.pack_start(self.orphan_title, True, True, 0)
        self.orphan_card.pack_start(orphan_header_box, False, False, 0)

        orphan_scroll = Gtk.ScrolledWindow()
        orphan_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        orphan_scroll.set_min_content_height(60)
        orphan_scroll.set_max_content_height(160)
        self.orphan_list = Gtk.ListBox()
        self.orphan_list.set_selection_mode(Gtk.SelectionMode.NONE)
        orphan_scroll.add(self.orphan_list)
        self.orphan_card.pack_start(orphan_scroll, True, True, 0)
        self.pack_start(self.orphan_card, False, False, 0)
        self.orphan_card.set_no_show_all(True)

        # ── Actions ───────────────────────────────────────────────────────────
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(10)
        actions.set_margin_bottom(12)

        self.remove_btn = Gtk.Button()
        btn_box = Gtk.Box(spacing=6)
        btn_box.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        btn_box.pack_start(Gtk.Label(label=_('Remove Selected')), False, False, 0)
        self.remove_btn.add(btn_box)
        self.remove_btn.get_style_context().add_class('destructive-action')
        self.remove_btn.connect('clicked', self._on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        actions.pack_start(self.remove_btn, False, False, 0)

        self.remove_orphans_btn = Gtk.Button()
        orphan_btn_box = Gtk.Box(spacing=6)
        orphan_btn_box.pack_start(Gtk.Image.new_from_icon_name('edit-delete', Gtk.IconSize.BUTTON), False, False, 0)
        orphan_btn_box.pack_start(Gtk.Label(label=_('Remove Orphaned Dirs')), False, False, 0)
        self.remove_orphans_btn.add(orphan_btn_box)
        self.remove_orphans_btn.get_style_context().add_class('destructive-action')
        self.remove_orphans_btn.connect('clicked', self._on_remove_orphans_clicked)
        self.remove_orphans_btn.set_sensitive(False)
        self.remove_orphans_btn.set_no_show_all(True)
        actions.pack_start(self.remove_orphans_btn, False, False, 0)

        self.pack_start(actions, False, False, 0)
        self.show_all()

    def populate(self, results: dict):
        self.store.clear()
        for row in self.orphan_list.get_children():
            self.orphan_list.remove(row)
        self._orphan_checks.clear()

        kernels  = results.get('kernels', [])
        removable = [k for k in kernels if not k.is_active]
        self.count_label.set_text(
            _('{} kernel(s) installed, {} removable').format(len(kernels), len(removable))
        )

        all_orphan_dirs = []

        for kernel in kernels:
            icon     = 'emblem-default' if kernel.is_active else 'user-trash'
            act_img  = not kernel.is_active and bool(kernel.image_pkg)
            act_hdr  = not kernel.is_active and bool(kernel.headers_pkg)
            act_src  = not kernel.is_active and bool(kernel.src_pkg)
            act_kbld = not kernel.is_active and bool(kernel.kbuild_pkg)

            self.store.append([
                icon,
                kernel.version,
                False, False, False, False,
                _fmt_size(kernel.size_kb * 1024),
                act_img, act_hdr, act_src, act_kbld,
                kernel,
            ])

            all_orphan_dirs.extend(kernel.orphan_src_dirs)
            all_orphan_dirs.extend(kernel.orphan_modules_dirs)

        # Orphaned dirs
        if all_orphan_dirs:
            for path in sorted(set(all_orphan_dirs)):
                row     = Gtk.ListBoxRow()
                row_box = Gtk.Box(spacing=12)
                row_box.set_margin_start(12)
                row_box.set_margin_top(4)
                row_box.set_margin_bottom(4)
                row_box.set_margin_end(12)

                check = Gtk.CheckButton()
                check.connect('toggled', self._on_orphan_check_toggled)
                self._orphan_checks[path] = check
                row_box.pack_start(check, False, False, 0)

                lbl = Gtk.Label(label=path)
                lbl.set_halign(Gtk.Align.START)
                lbl.get_style_context().add_class('dim-label')
                row_box.pack_start(lbl, True, True, 0)

                row.add(row_box)
                self.orphan_list.add(row)

            self.orphan_card.set_no_show_all(False)
            self.orphan_card.show_all()
            self.remove_orphans_btn.set_no_show_all(False)
            self.remove_orphans_btn.show()
        else:
            self.orphan_card.hide()
            self.remove_orphans_btn.hide()

        self.remove_btn.set_sensitive(False)
        self.remove_orphans_btn.set_sensitive(False)

    def _on_toggled(self, widget, path, col_idx):
        iter_ = self.store.get_iter(path)
        self.store[iter_][col_idx] = not self.store[iter_][col_idx]
        any_selected = any(row[2] or row[3] or row[4] or row[5] for row in self.store)
        self.remove_btn.set_sensitive(any_selected)

    def _on_orphan_check_toggled(self, check):
        any_selected = any(c.get_active() for c in self._orphan_checks.values())
        self.remove_orphans_btn.set_sensitive(any_selected)

    def _on_remove_clicked(self, btn):
        to_remove = []
        for row in self.store:
            k = row[11]
            if row[2] and k.image_pkg:
                to_remove.append(k.image_pkg)
                # Remove the metapackage together with the image so it doesn't
                # stay as an orphan and block future reinstalls from the Kernel Installer.
                if k.metapackage:
                    to_remove.append(k.metapackage)
            if row[3] and k.headers_pkg: to_remove.append(k.headers_pkg)
            if row[4] and k.src_pkg:     to_remove.append(k.src_pkg)
            if row[5] and k.kbuild_pkg:  to_remove.append(k.kbuild_pkg)

        if not to_remove:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Remove selected kernel packages?')
        )
        dialog.format_secondary_text(
            _('{} package(s) to remove:\n{}\n\nThe initramfs will be regenerated and GRUB updated.').format(
                len(to_remove),
                '\n'.join(to_remove[:5]) + ('...' if len(to_remove) > 5 else '')
            )
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_btn.set_sensitive(False)
        self.parent.set_ui_state(_('Removing kernel packages, regenerating initramfs and updating GRUB...'), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            if success:
                msg = _('Tasks completed successfully.')
            else:
                # do_apt_purge returns 'stderr', fallback to 'error' for other actions
                msg = result.get('error') or result.get('stderr') or _('Unknown error')
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(2, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state('', visible=False))

        self.parent.run_root_action(
            {'action': 'apt_purge', 'packages': to_remove},
            on_done
        )

    def _on_remove_orphans_clicked(self, btn):
        selected = [path for path, check in self._orphan_checks.items() if check.get_active()]
        if not selected:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Remove selected orphaned directories?')
        )
        dialog.format_secondary_text(
            _('{} director(y/ies) will be permanently deleted.').format(len(selected))
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_orphans_btn.set_sensitive(False)
        self.parent.set_ui_state(_('Removing orphaned kernel directories...'), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _('Orphaned directories removed.') if success else result.get('error', _('Unknown error'))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_orphans_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(2, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state('', visible=False))

        self.parent.run_root_action({'action': 'delete_orphan_dirs', 'paths': selected}, on_done)

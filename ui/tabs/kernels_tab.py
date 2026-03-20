"""
Kernels tab: list of installed kernels with selective removal.
Active kernel is always protected.
"""

import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class KernelsTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._kernel_checks = {}  # {version: {'image': check, 'headers': check, 'src': check}}
        self._build_ui()

    def _build_ui(self):
        info_box = Gtk.Box(spacing=10)
        info_box.set_margin_start(12)
        info_box.set_margin_end(12)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(8)

        self.count_label = Gtk.Label(label="")
        self.count_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.count_label, True, True, 0)
        self.pack_start(info_box, False, False, 0)

        # Scrolled window for TreeView in card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class('summary-card')
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        card.pack_start(scroll, True, True, 0)
        self.pack_start(card, True, True, 0)

        # ListStore: StatusIcon(str), Version(str), ImgChecked(bool), HdrChecked(bool), SrcChecked(bool), Size(str), ImgAct(bool), HdrAct(bool), SrcAct(bool), kernel(object)
        self.store = Gtk.ListStore(str, str, bool, bool, bool, str, bool, bool, bool, object)
        
        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.set_headers_visible(True)
        self.treeview.get_style_context().add_class('table-view')
        scroll.add(self.treeview)

        # Status Col
        renderer_icon = Gtk.CellRendererPixbuf()
        col_status = Gtk.TreeViewColumn("", renderer_icon, icon_name=0)
        self.treeview.append_column(col_status)

        # Version Col
        renderer_text = Gtk.CellRendererText()
        col_ver = Gtk.TreeViewColumn(_("Version"), renderer_text, text=1)
        col_ver.set_min_width(180)
        self.treeview.append_column(col_ver)

        # Image Col
        renderer_img = Gtk.CellRendererToggle()
        renderer_img.connect("toggled", self._on_toggled, 2)
        col_img = Gtk.TreeViewColumn(_("Image"), renderer_img, active=2, activatable=6)
        col_img.set_alignment(0.5)
        col_img.set_min_width(110)
        self.treeview.append_column(col_img)

        # Headers Col
        renderer_hdr = Gtk.CellRendererToggle()
        renderer_hdr.connect("toggled", self._on_toggled, 3)
        col_hdr = Gtk.TreeViewColumn(_("Headers"), renderer_hdr, active=3, activatable=7)
        col_hdr.set_alignment(0.5)
        col_hdr.set_min_width(110)
        self.treeview.append_column(col_hdr)

        # Sources Col
        renderer_src = Gtk.CellRendererToggle()
        renderer_src.connect("toggled", self._on_toggled, 4)
        col_src = Gtk.TreeViewColumn(_("Sources"), renderer_src, active=4, activatable=8)
        col_src.set_alignment(0.5)
        col_src.set_min_width(110)
        self.treeview.append_column(col_src)

        # Size Col
        renderer_size = Gtk.CellRendererText()
        renderer_size.set_property('xalign', 1.0)
        col_size = Gtk.TreeViewColumn(_("Size"), renderer_size, text=5)
        col_size.set_alignment(1.0)
        col_size.set_min_width(90)
        self.treeview.append_column(col_size)

        # Actions
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(10)
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
        self.store.clear()
        
        kernels = results.get('kernels', [])
        removable = [k for k in kernels if not k.is_active]
        self.count_label.set_text(
            _("{} kernel(s) installed, {} removable").format(len(kernels), len(removable))
        )

        for kernel in kernels:
            # emblem-default = green check, emblem-unreadable = red cross
            icon = 'emblem-default' if kernel.is_active else 'user-trash'
            
            act_img = not kernel.is_active and bool(kernel.image_pkg)
            act_hdr = not kernel.is_active and bool(kernel.headers_pkg)
            act_src = not kernel.is_active and bool(kernel.src_pkg)

            self.store.append([
                icon,
                kernel.version,
                False, False, False,
                _fmt_size(kernel.size_kb * 1024),
                act_img, act_hdr, act_src,
                kernel
            ])
            
        self.remove_btn.set_sensitive(False)

    def _on_toggled(self, widget, path, col_idx):
        iter_ = self.store.get_iter(path)
        self.store[iter_][col_idx] = not self.store[iter_][col_idx]
        
        any_selected = any(
            row[2] or row[3] or row[4] for row in self.store
        )
        self.remove_btn.set_sensitive(any_selected)

    def _on_remove_clicked(self, btn):
        to_remove = []
        for row in self.store:
            k = row[9]
            if row[2] and k.image_pkg: to_remove.append(k.image_pkg)
            if row[3] and k.headers_pkg: to_remove.append(k.headers_pkg)
            if row[4] and k.src_pkg: to_remove.append(k.src_pkg)

        if not to_remove:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected kernel packages?")
        )
        dialog.format_secondary_text(_("{} package(s) to remove:\n{}").format(
            len(to_remove), '\n'.join(to_remove[:5]) + ('...' if len(to_remove) > 5 else '')
        ))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_btn.set_sensitive(False)

        def do_purge():
            from cleaner.remover import purge_packages
            self.parent.set_ui_state(_("Removing kernel packages..."), pulse=True)
            success, msg = purge_packages(to_remove)

            GLib.idle_add(self.parent.set_ui_state, msg, 1.0 if success else 0.0, False, True)
            GLib.idle_add(self.remove_btn.set_sensitive, True)
            if success:
                GLib.timeout_add_seconds(2, lambda: self.parent.start_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        threading.Thread(target=do_purge, daemon=True).start()

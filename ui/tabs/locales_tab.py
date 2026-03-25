"""
Locales & Docs tab: Selective removal of languages and documentation.
Protects the current system language.
Supports DE-specific cleaners for Boro (Gnome) and Tyson (KDE).
"""

import os
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _, get_current_language
from core.environment import get_environment_detector
from utils.constants import fmt_size as _fmt_size


class LocalesTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._locales = []
        self._docs = []
        self._locale_checkboxes = {} # {path: check}
        self._doc_checkboxes = {}    # {path: check}
        self._pending_results = None
        self._protected_codes = set()
        self._build_ui()
        self.connect('map', self._on_mapped)

    def _build_ui(self):
        # Master toolbar
        toolbar = Gtk.Box(spacing=10)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)

        self.info_label = Gtk.Label(label=_("Select items to remove"))
        self.info_label.set_halign(Gtk.Align.START)
        toolbar.pack_start(self.info_label, True, True, 0)

        # Smart select button
        self.smart_btn = Gtk.Button(label=_("Keep only my languages"))
        self.smart_btn.set_tooltip_text(_("Unselect current language and English, select everything else"))
        self.smart_btn.connect('clicked', self._on_smart_select)
        toolbar.pack_end(self.smart_btn, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        # Main Container inside ScrolledWindow, wrapped in card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class('summary-card')
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        card.pack_start(scroll, True, True, 0)
        self.pack_start(card, True, True, 0)

        self.main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll.add_with_viewport(self.main_container)

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

    def populate(self, results: dict):
        # Clear any existing widgets immediately (fast)
        for child in self.main_container.get_children():
            child.destroy()
        self._locale_checkboxes.clear()
        self._doc_checkboxes.clear()

        if self.get_mapped():
            # Tab is currently visible — populate now
            self._do_populate(results)
        else:
            # Tab is hidden — defer widget creation until user switches to it
            self._pending_results = results

    def _on_mapped(self, widget):
        if self._pending_results is not None:
            results = self._pending_results
            self._pending_results = None
            self._do_populate(results)

    def _do_populate(self, results: dict):
        self._locales = results.get('locales', [])
        self._docs = results.get('docs_summary', [])

        # Precise language detection (System vs App)
        sys_lang_full = os.environ.get('LANG', 'en.UTF-8').split('.')[0] # 'es_ES', 'en_US', etc.
        sys_lang_base = sys_lang_full.split('_')[0]                     # 'es', 'en'
        app_lang_full = get_current_language()                          # Already a code like 'es' or 'en'

        # We protect exactly what is being used, plus C/POSIX defaults
        self._protected_codes = {sys_lang_full, sys_lang_base, app_lang_full, 'en', 'es', 'C', 'POSIX'}
        protected_codes = self._protected_codes

        # 1. System Documentation Card
        if self._docs:
            self._add_card_section(_("System Documentation"), self._docs, is_locale=False)

        # 2. Locales Section (grouped by category)
        categories = [
            ('system', _("Standard Locales"), 'locale'),
            ('gnome', _("Gnome Help files"), 'help-browser'),
            ('kde', _("KDE Documentation"), 'help-browser')
        ]

        for cat_id, cat_name, icon in categories:
            cat_items = [l for l in self._locales if l.category == cat_id]
            if cat_items:
                items_to_add = []
                for loc in sorted(cat_items, key=lambda x: x.code):
                    is_protected = loc.code in protected_codes
                    items_to_add.append((loc.name, loc.paths, loc.size_kb, icon, is_protected))
                self._add_card_section(cat_name, items_to_add, is_locale=True)

        self.main_container.show_all()

    def _add_card_section(self, title, items, is_locale=True):
        """Add a grouped section with separator."""
        # Add separator before section (except the very first)
        if self.main_container.get_children():
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.main_container.pack_start(sep, False, False, 0)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_margin_top(10)
        card.set_margin_bottom(10)
        card.set_margin_start(8)
        card.set_margin_end(8)

        # Section Header
        header = Gtk.Label()
        header.set_markup(f"<b>{title}</b>")
        header.set_halign(Gtk.Align.START)
        header.set_margin_bottom(4)
        card.pack_start(header, False, False, 0)

        # Items List
        for item in items:
            if is_locale:
                name, paths, size_kb, icon, protected = item
            else:
                # DocEntry: path es string, lo envolvemos en tupla
                name, paths, size_kb, icon, protected = item.name, (item.path,), item.size_kb, 'help-browser', False

            item_box = Gtk.Box(spacing=12)
            item_box.set_margin_start(8)
            item_box.set_margin_bottom(4)

            check = Gtk.CheckButton()
            if protected:
                check.set_active(False)
                check.set_sensitive(False)
                check.set_tooltip_text(_("Protected: current language or system default"))
            else:
                check.connect('toggled', self._on_check_toggled)
            
            if is_locale:
                self._locale_checkboxes[paths] = check
            else:
                self._doc_checkboxes[paths] = check
                
            item_box.pack_start(check, False, False, 0)

            img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
            item_box.pack_start(img, False, False, 0)

            lbl = Gtk.Label(label=name if isinstance(name, str) else paths[0])
            lbl.set_halign(Gtk.Align.START)
            if protected:
                lbl.get_style_context().add_class('dim-label')
            item_box.pack_start(lbl, True, True, 0)

            size_str = _fmt_size(size_kb * 1024)
            size_lbl = Gtk.Label(label=size_str)
            size_lbl.get_style_context().add_class('dim-label')
            item_box.pack_end(size_lbl, False, False, 0)

            card.pack_start(item_box, False, False, 0)

        self.main_container.pack_start(card, False, False, 0)


    def _on_check_toggled(self, check):
        any_loc = any(c.get_active() for c in self._locale_checkboxes.values() if c.get_sensitive())
        any_doc = any(c.get_active() for c in self._doc_checkboxes.values() if c.get_sensitive())
        self.remove_btn.set_sensitive(any_loc or any_doc)

    def _on_smart_select(self, btn):
        """Only toggle checkboxes for non-protected languages. Leave Docs alone."""
        for check in self._locale_checkboxes.values():
            if check.get_sensitive():
                check.set_active(True)

    def _on_remove_clicked(self, btn):
        combined = {**self._locale_checkboxes, **self._doc_checkboxes}
        selected_paths = []
        for paths, check in combined.items():
            if check.get_active():
                selected_paths.extend(paths)
        if not selected_paths:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Remove selected localization and documentation?")
        )
        dialog.format_secondary_text(_("{} items will be permanently deleted from the system.").format(len(selected_paths)))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_btn.set_sensitive(False)

        self.parent.set_ui_state(_("Cleaning locales and docs..."), pulse=True)
        def _on_done(result):
            success = result.get('success', False)
            msg = _("Localization and documentation cleaned successfully.") if success else result.get('error', _("Unknown error"))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state("", visible=False))

        self.parent.run_root_action({'action': 'delete_locales', 'paths': selected_paths, 'keep_codes': list(self._protected_codes)}, _on_done)

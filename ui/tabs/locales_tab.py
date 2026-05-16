"""
Locales & Docs tab: Selective removal of languages and documentation.
Protects the current system language.
Docs and languages have INDEPENDENT remove buttons — they never mix.
"""

import os
import subprocess
import configparser
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from core.i18n_manager import _, get_current_language
from utils.constants import fmt_size as _fmt_size


def _add_locale_str(protected: set, value: str):
    """Parse a locale string (or colon-separated list) and add all codes."""
    for entry in value.split(':'):
        entry = entry.split('.')[0].strip()  # drop encoding (UTF-8)
        entry = entry.split('@')[0].strip()  # drop modifier (@euro)
        if entry and entry not in ('C', 'POSIX'):
            protected.add(entry)             # e.g. 'fr_FR'
            protected.add(entry.split('_')[0])  # e.g. 'fr'


def _get_real_user_home() -> str | None:
    """
    When running as root via pkexec, returns the original user's home dir
    using PKEXEC_UID.  Falls back to HOME env var.
    """
    pkexec_uid = os.environ.get('PKEXEC_UID')
    if pkexec_uid:
        try:
            import pwd
            return pwd.getpwuid(int(pkexec_uid)).pw_dir
        except Exception:
            pass
    return os.environ.get('HOME')


def _detect_protected_codes() -> set[str]:
    """
    Detects the user's active locale codes across GNOME, KDE Plasma and XFCE.
    Sources (all additive):
      1. Environment variables (LANG, LANGUAGE, LC_ALL, LC_MESSAGES, LC_CTYPE)
      2. /etc/default/locale and /etc/locale.conf  (system-wide)
      3. GNOME — gsettings org.gnome.system.locale / desktop.interface
      4. KDE Plasma — ~/.config/plasma-localerc
      5. XFCE — ~/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml
                 (usually inherits system locale, but we check anyway)
      6. App language from get_current_language()
    Always preserves 'en', 'C', 'POSIX'.
    """
    protected = {'en', 'C', 'POSIX'}

    # ── 1. Environment variables ──────────────────────────────────────────────
    for var in ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LC_CTYPE'):
        val = os.environ.get(var, '').strip()
        if val:
            _add_locale_str(protected, val)

    # ── 2. System locale files ────────────────────────────────────────────────
    for locale_file in ('/etc/default/locale', '/etc/locale.conf'):
        try:
            with open(locale_file, 'r', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, _, val = line.partition('=')
                        if key.strip() in ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES'):
                            _add_locale_str(protected, val.strip().strip('"\''))
        except Exception:
            pass

    home = _get_real_user_home()

    # ── 3. GNOME (gsettings) ──────────────────────────────────────────────────
    try:
        for schema_key in (
            ('org.gnome.system.locale', 'region'),
            ('org.gnome.desktop.interface', 'gtk-language'),
        ):
            result = subprocess.run(
                ['gsettings', 'get', schema_key[0], schema_key[1]],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                val = result.stdout.strip().strip("'\"")
                if val:
                    _add_locale_str(protected, val)
    except Exception:
        pass

    # ── 4. KDE Plasma — ~/.config/plasma-localerc ─────────────────────────────
    if home:
        plasma_conf = os.path.join(home, '.config', 'plasma-localerc')
        try:
            cfg = configparser.ConfigParser(strict=False)
            cfg.read(plasma_conf, encoding='utf-8')
            for section in cfg.sections():
                for key in ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES'):
                    val = cfg.get(section, key, fallback='')
                    if val:
                        _add_locale_str(protected, val)
        except Exception:
            pass

        # KDE also stores language in kdeglobals [Translations] Language=
        kdeglobals = os.path.join(home, '.config', 'kdeglobals')
        try:
            cfg2 = configparser.ConfigParser(strict=False)
            cfg2.read(kdeglobals, encoding='utf-8')
            lang = cfg2.get('Translations', 'Language', fallback='')
            if lang:
                _add_locale_str(protected, lang)
        except Exception:
            pass

    # ── 5. XFCE — xsettings.xml (Net/IconThemeName area, locale via xfconf) ──
    # XFCE typically inherits system locale — the env vars above are sufficient.
    # We additionally check ~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-session.xml
    # in case there is a per-user override.
    if home:
        xfce_session = os.path.join(
            home, '.config', 'xfce4', 'xfconf',
            'xfce-perchannel-xml', 'xfce4-session.xml'
        )
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xfce_session)
            for prop in tree.iter('property'):
                name = prop.get('name', '')
                if 'lang' in name.lower() or 'locale' in name.lower():
                    val = prop.get('value', '')
                    if val:
                        _add_locale_str(protected, val)
        except Exception:
            pass

    # ── 6. App language ───────────────────────────────────────────────────────
    try:
        app_lang = get_current_language()
        if app_lang:
            _add_locale_str(protected, app_lang)
    except Exception:
        pass

    return protected


class LocalesTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._locales = []
        self._docs    = []
        self._locale_checkboxes = {}  # {paths tuple: check}
        self._doc_checkboxes    = {}  # {paths tuple: check}
        self._pending_results   = None
        self._protected_codes   = set()
        self._build_ui()
        self.connect('map', self._on_mapped)

    def _build_ui(self):
        # Toolbar
        toolbar = Gtk.Box(spacing=10)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)

        self.info_label = Gtk.Label(label=_('Select items to remove'))
        self.info_label.set_halign(Gtk.Align.START)
        toolbar.pack_start(self.info_label, True, True, 0)

        self.smart_btn = Gtk.Button(label=_('Keep only my languages'))
        self.smart_btn.set_tooltip_text(_('Select all languages except current language and English'))
        self.smart_btn.connect('clicked', self._on_smart_select)
        toolbar.pack_end(self.smart_btn, False, False, 0)

        self.select_docs_btn = Gtk.Button(label=_('Select all docs'))
        self.select_docs_btn.set_tooltip_text(_('Select all documentation entries'))
        self.select_docs_btn.connect('clicked', self._on_select_all_docs)
        toolbar.pack_end(self.select_docs_btn, False, False, 0)

        self.pack_start(toolbar, False, False, 0)

        # Scrollable content
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

        # ── Two independent action buttons ────────────────────────────────────
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(10)
        actions.set_margin_bottom(12)

        # Languages remove button
        self.remove_locales_btn = Gtk.Button()
        loc_box = Gtk.Box(spacing=6)
        loc_box.pack_start(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON), False, False, 0)
        loc_box.pack_start(Gtk.Label(label=_('Remove selected languages')), False, False, 0)
        self.remove_locales_btn.add(loc_box)
        self.remove_locales_btn.get_style_context().add_class('destructive-action')
        self.remove_locales_btn.connect('clicked', self._on_remove_locales_clicked)
        self.remove_locales_btn.set_sensitive(False)
        actions.pack_start(self.remove_locales_btn, False, False, 0)

        # Docs remove button
        self.remove_docs_btn = Gtk.Button()
        doc_box = Gtk.Box(spacing=6)
        doc_box.pack_start(Gtk.Image.new_from_icon_name('user-trash', Gtk.IconSize.BUTTON), False, False, 0)
        doc_box.pack_start(Gtk.Label(label=_('Remove selected docs')), False, False, 0)
        self.remove_docs_btn.add(doc_box)
        self.remove_docs_btn.get_style_context().add_class('destructive-action')
        self.remove_docs_btn.connect('clicked', self._on_remove_docs_clicked)
        self.remove_docs_btn.set_sensitive(False)
        actions.pack_start(self.remove_docs_btn, False, False, 0)

        self.pack_start(actions, False, False, 0)
        self.show_all()

    def populate(self, results: dict):
        for child in self.main_container.get_children():
            child.destroy()
        self._locale_checkboxes.clear()
        self._doc_checkboxes.clear()

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
        self._locales = results.get('locales', [])
        self._docs    = results.get('docs_summary', [])

        self._protected_codes = _detect_protected_codes()
        protected_codes = self._protected_codes

        # System Documentation section
        if self._docs:
            self._add_card_section(_('System Documentation'), self._docs, is_locale=False)

        # Locale sections grouped by category
        categories = [
            ('system', _('Standard Locales'),    'locale'),
            ('gnome',  _('Gnome Help files'),     'help-browser'),
            ('kde',    _('KDE Documentation'),    'help-browser'),
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
        if self.main_container.get_children():
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.main_container.pack_start(sep, False, False, 0)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_margin_top(10)
        card.set_margin_bottom(10)
        card.set_margin_start(8)
        card.set_margin_end(8)

        header = Gtk.Label()
        header.set_markup(f'<b>{title}</b>')
        header.set_halign(Gtk.Align.START)
        header.set_margin_bottom(4)
        card.pack_start(header, False, False, 0)

        for item in items:
            if is_locale:
                name, paths, size_kb, icon, protected = item
            else:
                name, paths, size_kb, icon, protected = (
                    item.name, (item.path,), item.size_kb, 'help-browser', False
                )

            item_box = Gtk.Box(spacing=12)
            item_box.set_margin_start(8)
            item_box.set_margin_bottom(4)

            check = Gtk.CheckButton()
            if protected:
                check.set_active(False)
                check.set_sensitive(False)
                check.set_tooltip_text(_('Protected: current language or system default'))
            else:
                if is_locale:
                    check.connect('toggled', self._on_locale_check_toggled)
                else:
                    check.connect('toggled', self._on_doc_check_toggled)

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

            size_lbl = Gtk.Label(label=_fmt_size(size_kb * 1024))
            size_lbl.get_style_context().add_class('dim-label')
            item_box.pack_end(size_lbl, False, False, 0)

            card.pack_start(item_box, False, False, 0)

        self.main_container.pack_start(card, False, False, 0)

    # ── Toggle callbacks ──────────────────────────────────────────────────────

    def _on_locale_check_toggled(self, check):
        any_selected = any(
            c.get_active() for c in self._locale_checkboxes.values() if c.get_sensitive()
        )
        self.remove_locales_btn.set_sensitive(any_selected)

    def _on_doc_check_toggled(self, check):
        any_selected = any(
            c.get_active() for c in self._doc_checkboxes.values() if c.get_sensitive()
        )
        self.remove_docs_btn.set_sensitive(any_selected)

    def _on_smart_select(self, btn):
        """Select all non-protected language checkboxes. Leaves docs untouched."""
        for check in self._locale_checkboxes.values():
            if check.get_sensitive():
                check.set_active(True)

    def _on_select_all_docs(self, btn):
        """Select all documentation checkboxes. Leaves languages untouched."""
        for check in self._doc_checkboxes.values():
            if check.get_sensitive():
                check.set_active(True)

    # ── Remove actions (completely independent) ───────────────────────────────

    def _on_remove_locales_clicked(self, btn):
        """Remove only selected languages. Invokes localepurge."""
        selected_paths = []
        for paths, check in self._locale_checkboxes.items():
            if check.get_active():
                selected_paths.extend(paths)
        if not selected_paths:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Remove selected languages?')
        )
        dialog.format_secondary_text(
            _('{} language path(s) will be permanently deleted.').format(len(selected_paths))
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_locales_btn.set_sensitive(False)
        self.parent.set_ui_state(_('Removing languages...'), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _('Languages removed successfully.') if success else result.get('error', _('Unknown error'))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_locales_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state('', visible=False))

        self.parent.run_root_action(
            {'action': 'delete_locales', 'paths': selected_paths, 'keep_codes': list(self._protected_codes)},
            on_done
        )

    def _on_remove_docs_clicked(self, btn):
        """Remove only selected documentation. Does NOT invoke localepurge."""
        selected_paths = []
        for paths, check in self._doc_checkboxes.items():
            if check.get_active():
                selected_paths.extend(paths)
        if not selected_paths:
            return

        dialog = Gtk.MessageDialog(
            parent=self.parent, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Remove selected documentation?')
        )
        dialog.format_secondary_text(
            _('{} documentation path(s) will be permanently deleted.').format(len(selected_paths))
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self.remove_docs_btn.set_sensitive(False)
        self.parent.set_ui_state(_('Removing documentation...'), pulse=True)

        def on_done(result):
            success = result.get('success', False)
            msg = _('Documentation removed successfully.') if success else result.get('error', _('Unknown error'))
            self.parent.set_ui_state(msg, 1.0 if success else 0.0, False, True)
            self.remove_docs_btn.set_sensitive(True)
            if success:
                GLib.timeout_add_seconds(1, lambda: self.parent.start_root_scan())
            GLib.timeout_add_seconds(4, lambda: self.parent.set_ui_state('', visible=False))

        self.parent.run_root_action(
            {'action': 'delete_docs', 'paths': selected_paths},
            on_done
        )

"""
Overview tab: shows a summary of all scan results with total reclaimable space.
"""

import os
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf

from core.i18n_manager import _
from utils.constants import fmt_size as _fmt_size


class OverviewTab(Gtk.Box):

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent = parent_window
        self._sys_timer_id = None
        self._build_placeholder()

    def _build_placeholder(self):
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        placeholder.set_valign(Gtk.Align.CENTER)
        placeholder.set_halign(Gtk.Align.CENTER)

        # Clickable scan icon (EventBox to avoid button frame)
        soplos_icon = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'soplos.png'))
        if os.path.exists(soplos_icon):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(soplos_icon, 128, 128, True)
            scan_icon = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            scan_icon = Gtk.Image.new_from_icon_name('system-search', Gtk.IconSize.DIALOG)
            scan_icon.set_pixel_size(128)
        event_box = Gtk.EventBox()
        event_box.add(scan_icon)
        event_box.set_visible_window(False)
        event_box.connect('button-press-event', lambda w, e: self.parent._on_scan_clicked())
        event_box.set_tooltip_text(_("Scan system"))
        placeholder.pack_start(event_box, False, False, 0)

        label = Gtk.Label()
        label.set_markup(f"<span size='large'>{_('Click the icon to analyze the system')}</span>")
        label.set_justify(Gtk.Justification.CENTER)
        placeholder.pack_start(label, False, False, 0)

        sub = Gtk.Label()
        sub.set_markup(f"<span color='gray'>{_('The scan may take a few seconds')}</span>")
        placeholder.pack_start(sub, False, False, 0)

        if os.geteuid() != 0:
            admin_label = Gtk.Label()
            admin_label.set_markup(f'<a href="#">{_("Run as administrator")}</a>')
            admin_label.connect('activate-link', lambda lbl, uri: self.parent.start_root_scan() or True)
            placeholder.pack_start(admin_label, False, False, 0)

        self.pack_start(placeholder, True, True, 40)
        self._placeholder = placeholder
        self.show_all()

    def _update_sys_usage(self):
        if not hasattr(self, 'sys_count_label') or not self.get_mapped():
            return True
        threading.Thread(target=self._read_sys_stats, daemon=True).start()
        return True

    def _read_sys_stats(self):
        try:
            with open('/proc/stat', 'r') as f:
                lines = f.readlines()
            cpu_parts = [int(p) for p in lines[0].split()[1:]]
            idle = cpu_parts[3]
            total = sum(cpu_parts)

            if hasattr(self, '_last_cpu'):
                idle_delta = idle - self._last_cpu[0]
                total_delta = total - self._last_cpu[1]
                cpu_usage = 100.0 * (1.0 - idle_delta / total_delta) if total_delta > 0 else 0.0
            else:
                cpu_usage = 0.0
            self._last_cpu = (idle, total)

            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split()
                mem[parts[0].strip(':')] = int(parts[1])
            total_m = mem['MemTotal']
            free_m = mem['MemFree']
            buffers_m = mem.get('Buffers', 0)
            cached_m = mem.get('Cached', 0)
            used_m = total_m - free_m - buffers_m - cached_m
            ram_usage = (used_m / total_m) * 100.0

            st = os.statvfs('/')
            disk_total = st.f_blocks * st.f_frsize
            disk_free = st.f_bavail * st.f_frsize
            disk_used = disk_total - disk_free
            disk_usage = (disk_used / disk_total) * 100.0

            temp = "--"
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                try:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        t = int(f.read().strip()) / 1000.0
                    temp = f"{t:.1f}°C"
                except Exception:
                    pass

            cpu_text = f"CPU: <b>{cpu_usage:.1f}%</b>   RAM: <b>{ram_usage:.1f}%</b>"
            disk_text = f"DISK: <b>{disk_usage:.1f}%</b>   TEMP: <b>{temp}</b>"
            GLib.idle_add(self._apply_sys_labels, cpu_text, disk_text)
        except Exception:
            pass

    def _apply_sys_labels(self, cpu_text, disk_text):
        if hasattr(self, 'sys_count_label'):
            self.sys_count_label.set_markup(cpu_text)
            self.sys_size_label.set_markup(disk_text)
        return False

    def populate(self, results: dict):
        # Clear
        for child in self.get_children():
            child.destroy()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(scroll, True, True, 0)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        outer.set_margin_top(15)
        outer.set_margin_bottom(15)
        outer.set_margin_start(15)
        outer.set_margin_end(15)
        scroll.add(outer)

        # Title
        title = Gtk.Label()
        title.set_markup(f"<b><span size='large'>{_('Scan Summary')}</span></b>")
        title.set_halign(Gtk.Align.START)
        outer.pack_start(title, False, False, 0)

        # Summary cards grid
        grid = Gtk.Grid(row_spacing=10, column_spacing=10)
        grid.set_halign(Gtk.Align.FILL)
        grid.set_column_homogeneous(True)
        outer.pack_start(grid, False, False, 0)

        # System Usage Metrics (always shown)
        card_sys, sys_cnt, sys_sz = self._make_card('utilities-system-monitor', _("System Usage"), "CPU: --%", "RAM: --%", ret_labels=True)
        self.sys_count_label = sys_cnt
        self.sys_size_label = sys_sz
        if self._sys_timer_id is not None:
            GLib.source_remove(self._sys_timer_id)
        self._sys_timer_id = GLib.timeout_add_seconds(1, self._update_sys_usage)

        # User cards (always shown)
        cache_entries = results.get('user_cache_entries', [])
        cache_size = sum(e.size_bytes for e in cache_entries)
        card_cache = self._make_card('folder', _("User Cache"), _("{} item(s)").format(len(cache_entries)), _fmt_size(cache_size))

        trash = results.get('trash_info')
        trash_count = trash.files_count if trash else 0
        trash_size = trash.size_bytes if trash else 0
        card_trash = self._make_card('user-trash-full', _("Trash"), _("{} item(s)").format(trash_count), _fmt_size(trash_size))

        flatpak_entries = results.get('flatpak_entries', [])
        flatpak_size = sum(e.size_bytes for e in flatpak_entries)
        card_flatpak = self._make_card('package-x-generic', _("Flatpak"), _("{} unused").format(len(flatpak_entries)), _fmt_size(flatpak_size))

        has_root_data = os.geteuid() == 0 or 'kernels' in results

        if has_root_data:
            gpu_pkgs = results.get('unnecessary_pkgs', [])
            gpu_size = sum((p.installed_size if not isinstance(p, dict) else p.get('installed_size', 0)) * 1024 for p in gpu_pkgs)
            card_gpu = self._make_card('video-display', _("Unnecessary GPU Drivers"), _("{} item(s)").format(len(gpu_pkgs)), _fmt_size(gpu_size))

            kernels = [k for k in results.get('kernels', []) if (not k.is_active if not isinstance(k, dict) else not k.get('is_active', False))]
            kernel_size = sum((k.size_kb if not isinstance(k, dict) else k.get('size_kb', 0)) * 1024 for k in kernels)
            card_kernels = self._make_card('media-flash', _("Old Kernels"), _("{} item(s)").format(len(kernels)), _fmt_size(kernel_size))

            apt_info = results.get('apt_cache', {})
            apt_size = apt_info.get('size_bytes', 0)
            apt_count = apt_info.get('deb_count', 0)
            card_apt = self._make_card('system-software-install', _("APT Cache"), f"{apt_count} .deb", _fmt_size(apt_size))

            temp_entries = results.get('temp_entries', [])
            temp_size = sum((e.size_bytes if not isinstance(e, dict) else e.get('size_bytes', 0)) for e in temp_entries)
            card_temp = self._make_card('user-trash', _("Temporary Files"), _("{} item(s)").format(len(temp_entries)), _fmt_size(temp_size))

            firmwares = results.get('firmware_families', [])
            is_protected = results.get('is_firmware_protected', lambda x: False)
            unprotected_count = sum(1 for f in firmwares if not is_protected(f))
            card_fw = self._make_card('drive-harddisk', _("Firmware Families"), _("{} family(s)").format(len(firmwares)), _("{} removable").format(unprotected_count))

            locales = results.get('locales', [])
            docs = results.get('docs_summary', [])
            lang_size = (sum(l.size_kb if not isinstance(l, dict) else l.get('size_kb', 0) for l in locales) + 
                         sum(d.size_kb if not isinstance(d, dict) else d.get('size_kb', 0) for d in docs)) * 1024
            card_lang = self._make_card('locale', _("Languages & Docs"), _("{} item(s)").format(len(locales) + len(docs)), _fmt_size(lang_size))

            log_entries = results.get('log_entries', [])
            log_size = sum(e.get('size_bytes', 0) if isinstance(e, dict) else e.size_bytes for e in log_entries)
            journald = results.get('journald', {})
            journald_size = journald.get('size_bytes', 0) if isinstance(journald, dict) else 0
            card_logs = self._make_card('text-x-script', _("System Logs"), _("{} item(s)").format(len(log_entries)), _fmt_size(log_size + journald_size))

            total = gpu_size + kernel_size + apt_size + temp_size + lang_size + log_size + journald_size
            card_total = self._make_card('edit-clear', _("Total Reclaimable Space"), _("Ready to clean"), _fmt_size(total))

            cards = [card_gpu, card_kernels, card_apt,
                     card_temp, card_fw, card_lang,
                     card_logs, card_total, card_sys]
        else:
            apps = results.get('installed_apps', [])
            apps_count = len(apps)
            apps_size = sum((a['size_kb'] if isinstance(a, dict) else a.size_kb) for a in apps) * 1024
            card_apps = self._make_card('application-x-executable', _("Installed Apps"), _("{} package(s)").format(apps_count), _fmt_size(apps_size))

            snap_revisions = results.get('snap_revisions', [])
            snap_size = sum(r['size_bytes'] if isinstance(r, dict) else r.size_bytes for r in snap_revisions)
            card_snap = self._make_card('package-x-generic', _("Snap"), _("{} old revision(s)").format(len(snap_revisions)), _fmt_size(snap_size))

            total = cache_size + trash_size + flatpak_size + snap_size
            card_total = self._make_card('edit-clear', _("Total Reclaimable Space"), _("Ready to clean"), _fmt_size(total))
            cards = [card_apps, card_flatpak, card_snap, card_cache, card_trash, card_total, card_sys]

        if os.geteuid() != 0 and not has_root_data:
            admin_label = Gtk.Label()
            admin_label.set_markup(f'<a href="#">{_("Run as administrator")}</a>')
            admin_label.connect('activate-link', lambda lbl, uri: self.parent.start_root_scan() or True)
            outer.pack_start(admin_label, False, False, 0)

        for i, c in enumerate(cards):
            c.set_hexpand(True)
            grid.attach(c, i % 3, i // 3, 1, 1)

        self.show_all()

    def _make_card(self, icon_name: str, title: str, count: str, size: str, ret_labels=False) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class('summary-card')
        card.set_margin_top(0)
        card.set_margin_bottom(0)
        card.set_margin_start(0)
        card.set_margin_end(0)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
        header_box.pack_start(icon, False, False, 0)
        title_label = Gtk.Label(label=title)
        title_label.get_style_context().add_class('summary-card-title')
        title_label.set_line_wrap(True)
        header_box.pack_start(title_label, True, True, 0)
        card.pack_start(header_box, False, False, 0)

        count_label = Gtk.Label(label=count)
        count_label.set_halign(Gtk.Align.START)
        card.pack_start(count_label, False, False, 0)

        size_label = Gtk.Label(label=size)
        size_label.get_style_context().add_class('summary-card-value')
        size_label.set_halign(Gtk.Align.START)
        size_label.set_line_wrap(True)
        card.pack_start(size_label, False, False, 0)

        if ret_labels:
            return card, count_label, size_label
        return card

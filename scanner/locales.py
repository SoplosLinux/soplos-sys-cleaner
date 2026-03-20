"""
Scanner for language and documentation files.
Supports standard locales and DE-specific paths (Gnome Help, KDE HTML).
"""

import os
import subprocess
from typing import NamedTuple


class LocaleEntry(NamedTuple):
    code: str
    name: str # Human readable if possible, or same as code
    path: str
    size_kb: int
    category: str # 'system', 'gnome', 'kde'


class DocEntry(NamedTuple):
    name: str
    path: str
    size_kb: int
    type: str # 'man', 'info', 'doc'


def _get_dir_size_kb(path: str) -> int:
    """Calculate directory size in KB using 'du' for speed and accuracy."""
    if not os.path.isdir(path):
        return 0
    try:
        # du -sk returns size in blocks (1K blocks)
        res = subprocess.run(['du', '-sk', path], capture_output=True, text=True, check=True)
        size_str = res.stdout.split()[0]
        return int(size_str)
    except Exception:
        return 0


def get_locales_info(desktop: str) -> list[LocaleEntry]:
    """Retrieve list of installed locales and desktop-specific help files."""
    results = {} # Use dict to group by locale code: {code: LocaleEntry}
    
    # 1. Standard Locales (/usr/share/locale)
    base_path = "/usr/share/locale"
    if os.path.isdir(base_path):
        try:
            for entry in os.scandir(base_path):
                if entry.is_dir() and len(entry.name) <= 12: 
                    size = _get_dir_size_kb(entry.path)
                    if size > 0:
                        results[entry.name] = LocaleEntry(
                            code=entry.name,
                            name=entry.name,
                            path=entry.path,
                            size_kb=size,
                            category='system'
                        )
        except (OSError, PermissionError):
            pass

    # 2. Desktop Help (/usr/share/help) - Consolidate by language
    # Covers Boro (Gnome), Tyron (XFCE) and now Tyson (KDE)
    help_path = "/usr/share/help"
    if os.path.isdir(help_path):
        try:
            for app_entry in os.scandir(help_path):
                if app_entry.is_dir():
                    try:
                        for lang_entry in os.scandir(app_entry.path):
                            if lang_entry.is_dir() and len(lang_entry.name) <= 5:
                                code = lang_entry.name
                                size = _get_dir_size_kb(lang_entry.path)
                                if size > 0:
                                    if code in results:
                                        old = results[code]
                                        results[code] = old._replace(size_kb=old.size_kb + size)
                                    else:
                                        results[code] = LocaleEntry(
                                            code=code,
                                            name=code,
                                            path=lang_entry.path,
                                            size_kb=size,
                                            category='gnome' # Group all help here
                                        )
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass

    # 3. KDE HTML fallback (/usr/share/doc/HTML)
    kde_path = "/usr/share/doc/HTML"
    if os.path.isdir(kde_path):
        try:
            for entry in os.scandir(kde_path):
                if entry.is_dir() and len(entry.name) <= 5:
                    code = entry.name
                    size = _get_dir_size_kb(entry.path)
                    if size > 0:
                        if code in results:
                            old = results[code]
                            results[code] = old._replace(size_kb=old.size_kb + size)
                        else:
                            results[code] = LocaleEntry(
                                code=code,
                                name=code,
                                path=entry.path,
                                size_kb=size,
                                category='kde'
                            )
        except (OSError, PermissionError):
            pass
    
    return list(results.values())


def get_docs_summary() -> list[DocEntry]:
    """Retrieve summary of extended system documentation sizes."""
    # Comprehensive list of documentation roots discovered across Boro, Tyron, Tyson
    doc_roots = [
        ('Manual Pages', '/usr/share/man', 'man'),
        ('Info Pages', '/usr/share/info', 'info'),
        ('Package Documentation', '/usr/share/doc', 'doc'),
        ('Qt5 Documentation', '/usr/share/qt5/doc', 'doc'),
        ('Qt6 Documentation', '/usr/share/qt6/doc', 'doc'),
        ('GTK Documentation', '/usr/share/gtk-doc', 'doc'),
        ('CUPS Documentation', '/usr/share/cups/doc-root', 'doc'),
        ('DocBook XML', '/usr/share/xml/docbook', 'doc'),
        ('Doc-Base', '/usr/share/doc-base', 'doc'),
        ('XFCE Helpers', '/usr/share/xfce4/helpers', 'doc'),
        ('KF6 DocTools', '/usr/share/kf6/kdoctools', 'doc'),
        ('Developer Help', '/usr/share/devhelp', 'doc'),
        ('Soplos App Docs', '/usr/share/soplos-welcome/docs', 'doc'),
    ]
    
    results = []
    for name, path, dtype in doc_roots:
        if os.path.exists(path):
            size = _get_dir_size_kb(path)
            if size > 0:
                results.append(DocEntry(name, path, size, dtype))
    return results

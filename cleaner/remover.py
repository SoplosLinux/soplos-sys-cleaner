"""
Package and file removal logic for Soplos Sys Cleaner.
All destructive operations are here.
"""

import subprocess
import shutil
import os
import shlex
from core.i18n_manager import _
from typing import Callable


def purge_packages(packages: list[str], progress_cb: Callable = None) -> tuple[bool, str]:
    """Purge packages and autoremove dependencies in a single session."""
    return purge_and_rebuild(packages, rebuild_initrd=False, progress_cb=progress_cb)


def purge_and_rebuild(packages: list[str], rebuild_initrd: bool = False, progress_cb: Callable = None) -> tuple[bool, str]:
    """
    Combined operation: purge + autoremove [+ dracut].
    Uses a single pkexec session to avoid multiple password prompts.
    """
    if not packages:
        return True, _("No packages to remove.")

    if progress_cb:
        progress_cb(0.1, _("Preparing administrative tasks..."))

    # Sanitize package names
    pkg_str = " ".join(shlex.quote(p) for p in packages)
    
    # Build commands sequence
    cmds = [
        f"apt-get purge -y --allow-remove-essential=false {pkg_str}",
        "apt-get autoremove -y"
    ]
    if rebuild_initrd:
        cmds.append("dracut -f")

    full_shell_cmd = " && ".join(cmds)

    try:
        result = subprocess.run(
            ['pkexec', 'bash', '-c', full_shell_cmd],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            # pkexec return code 127 usually means the user cancelled the dialog
            if result.returncode == 127:
                return False, _("Authentication cancelled.")
            return False, f"Error: {result.stderr.strip() or result.stdout.strip()}"

        return True, _("Tasks completed successfully.")

    except Exception as e:
        return False, _("Unexpected error: {}").format(e)


def clean_apt_cache(progress_cb: Callable = None) -> tuple[bool, str]:
    """Run apt-get clean to clear the APT cache."""
    if progress_cb:
        progress_cb(0.2, _("Cleaning APT cache..."))
    try:
        subprocess.run(['pkexec', 'apt-get', 'clean'], check=True)
        return True, _("APT cache cleaned successfully.")
    except Exception as e:
        return False, _("Error cleaning cache: {}").format(e)


def autoremove_packages(progress_cb: Callable = None) -> tuple[bool, str]:
    """Run apt-get autoremove to remove orphaned packages."""
    if progress_cb:
        progress_cb(0.2, _("Removing orphaned packages..."))
    try:
        result = subprocess.run(
            ['pkexec', 'apt-get', 'autoremove', '-y'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return False, f"Error: {result.stderr.strip()}"
        return True, _("Orphaned packages removed.")
    except Exception as e:
        return False, f"Error: {e}"


def delete_temp_paths(paths: list[str], progress_cb: Callable = None) -> tuple[bool, str]:
    """Remove temporary files and directories."""
    removed = 0
    errors = []
    total = len(paths)

    for i, path in enumerate(paths):
        if progress_cb:
            progress_cb((i + 1) / total * 1.0, _("Removing {}...").format(os.path.basename(path)))
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                try:
                    os.remove(path)
                except PermissionError:
                    pass # Ignore permission errors
            removed += 1
        except Exception as e:
            errors.append(_("Error in {}: {}").format(path, e))

    msg = _("{} item(s) removed.").format(removed)
    if errors:
        msg += " " + _("{} error(s).").format(len(errors))
    return len(errors) == 0, msg


def rebuild_initrd(progress_cb: Callable = None) -> tuple[bool, str]:
    """Trigger dracut to rebuild initramfs after driver/firmware changes."""
    if progress_cb:
        progress_cb(0.5, _("Regenerating initramfs with dracut..."))
    try:
        result = subprocess.run(
            ['pkexec', 'dracut', '-f'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            if result.returncode == 127:
                return False, _("Authentication cancelled.")
            return False, _("dracut error: {}").format(result.stderr.strip())
        return True, _("initramfs regenerated successfully.")
    except FileNotFoundError:
        return False, _("dracut not found on the system.")
    except Exception as e:
        return False, _("Unexpected error: {}").format(e)


def remove_firmware_and_rebuild(families: list[str], progress_cb: Callable = None) -> tuple[bool, str]:
    """
    Remove firmware directories and rebuild initrd in ONE pkexec session.
    """
    if not families:
        return True, _("No firmwares to remove.")

    if progress_cb:
        progress_cb(0.1, _("Preparing firmware removal..."))

    # Build paths and command
    paths = [shlex.quote(f"/lib/firmware/{f}") for f in families]
    rm_cmd = f"rm -rf {' '.join(paths)}"
    full_shell_cmd = f"{rm_cmd} && dracut -f"

    try:
        result = subprocess.run(
            ['pkexec', 'bash', '-c', full_shell_cmd],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            if result.returncode == 127:
                return False, _("Authentication cancelled.")
            return False, f"Error: {result.stderr.strip() or result.stdout.strip()}"

        return True, _("Firmware removed and initramfs regenerated.")

    except Exception as e:
        return False, _("Unexpected error: {}").format(e)


def purge_locales_and_docs(paths: list[str], keep_codes: list[str] = None, progress_cb: Callable = None) -> tuple[bool, str]:
    """
    Remove locale/doc directories and configure localepurge in a single pkexec session.
    localepurge prevents APT from restoring deleted locales on future upgrades.
    """
    if not paths:
        return True, _("No items selected for removal.")

    if progress_cb:
        progress_cb(0.1, _("Cleaning localization and documentation files..."))

    safe_paths = [shlex.quote(p) for p in paths]
    cmds = [f"rm -rf {' '.join(safe_paths)}"]

    if keep_codes:
        codes = sorted(set(keep_codes))
        nopurge_content = "# Generated by Soplos Sys Cleaner\n"
        nopurge_content += "NEEDSCONFIGUPDATE=0\n"
        nopurge_content += "VERBOSE=0\n"
        nopurge_content += "SHOWFREEDSPACE=1\n"
        nopurge_content += "DONTBOTHERNEWLOCALE\n"
        for code in codes:
            nopurge_content += f"{code}\n"

        # Install localepurge if missing, write config, and run it
        cmds.append(
            "command -v localepurge >/dev/null 2>&1 || "
            "DEBIAN_FRONTEND=noninteractive apt-get install -y localepurge"
        )
        cmds.append(f"printf '%s' {shlex.quote(nopurge_content)} > /etc/locale.nopurge")
        cmds.append("localepurge")

    try:
        result = subprocess.run(
            ['pkexec', 'bash', '-c', ' && '.join(cmds)],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            if result.returncode == 127:
                return False, _("Authentication cancelled.")
            return False, f"Error: {result.stderr.strip() or result.stdout.strip()}"

        return True, _("Localization and documentation cleaned successfully.")

    except Exception as e:
        return False, _("Unexpected error: {}").format(e)

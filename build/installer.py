"""Single-file per-user installer for Dirt Gear."""
from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from zipfile import ZipFile


APP_NAME = 'Dirt Gear'


def version() -> str:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    for path in (root / 'VERSION.txt', root.parent / 'VERSION.txt'):
        if path.is_file():
            return path.read_text(encoding='utf-8').strip()
    return ''


TITLE = f'Dirt Gear v{version()} Setup' if version() else 'Dirt Gear Setup'


def payload_path() -> Path:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    return root / 'payload.zip'


def within(parent: Path, child: Path) -> bool:
    return child.resolve().is_relative_to(parent.resolve())


def shortcut(path: Path, executable: Path) -> None:
    quoted_path = str(path).replace("'", "''")
    quoted_exe = str(executable).replace("'", "''")
    quoted_working = str(executable.parent).replace("'", "''")
    script = (
        f"$link=(New-Object -ComObject WScript.Shell).CreateShortcut('{quoted_path}');"
        f"$link.TargetPath='{quoted_exe}';"
        f"$link.WorkingDirectory='{quoted_working}';"
        f"$link.IconLocation='{quoted_exe}';"
        "$link.Save()"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                   check=True, capture_output=True, text=True, timeout=30)


def windows_folder(name: str) -> Path:
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
         f"[Environment]::GetFolderPath('{name}')"],
        check=True, capture_output=True, text=True, timeout=30,
    )
    folder = result.stdout.strip()
    candidates = [Path(folder)] if folder else []
    if name == 'DesktopDirectory':
        if os.environ.get('OneDrive'):
            candidates.append(Path(os.environ['OneDrive']) / 'Desktop')
        candidates.append(Path.home() / 'OneDrive/Desktop')
        candidates.append(Path.home() / 'Desktop')
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise ValueError(f'Windows could not find the {name} folder.')


def refresh_icons() -> None:
    """Ask Windows to redraw shortcut icons (it caches them, so an updated
    app icon otherwise keeps showing the old picture)."""
    if os.name != 'nt':
        return
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass
    try:
        subprocess.run(['ie4uinit.exe', '-show'], capture_output=True, timeout=20)
    except Exception:
        pass


def refresh_shortcuts(executable: Path) -> None:
    """Re-create existing Desktop/Start menu shortcuts so they pick up the new icon."""
    for folder in ('DesktopDirectory', 'Programs'):
        try:
            link = windows_folder(folder) / 'Dirt Gear.lnk'
            if link.exists():
                link.unlink()
                shortcut(link, executable)
        except Exception:
            continue


def install(target: Path, make_shortcuts: bool = True) -> Path:
    target = target.expanduser().resolve()
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / f'.dirt-gear-install-{uuid.uuid4().hex}'
    backup = parent / f'.dirt-gear-previous-{uuid.uuid4().hex}'
    if not within(parent, stage) or not within(parent, backup) or not within(parent, target):
        raise ValueError('Unsafe installation path')
    previous = False
    try:
        stage.mkdir()
        with ZipFile(payload_path()) as archive:
            for member in archive.infolist():
                destination = stage / member.filename
                if not within(stage, destination):
                    raise ValueError('The installer contains an invalid path.')
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open('wb') as out:
                    shutil.copyfileobj(source, out)
        executable = stage / 'Dirt Gear.exe'
        if not executable.is_file() or not (stage / '_internal/static/app.js').is_file():
            raise ValueError('The installer payload is incomplete.')
        if target.exists():
            # Right after the app closes Windows can hold its files briefly.
            for attempt in range(20):
                try:
                    target.rename(backup)
                    break
                except PermissionError:
                    if attempt == 19:
                        raise
                    time.sleep(1)
            previous = True
        try:
            stage.rename(target)
        except Exception:
            if previous:
                backup.rename(target)
            raise
        if make_shortcuts:
            desktop = windows_folder('DesktopDirectory')
            programs = windows_folder('Programs')
            shortcut(desktop / 'Dirt Gear.lnk', target / 'Dirt Gear.exe')
            shortcut(programs / 'Dirt Gear.lnk', target / 'Dirt Gear.exe')
        if previous and backup.exists():
            shutil.rmtree(backup)
        refresh_icons()
        return target / 'Dirt Gear.exe'
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def show_installer(target: Path, make_shortcuts: bool = True) -> bool:
    """Use Windows' built-in dialogs; the EXE needs no Tk installation."""
    user32 = ctypes.windll.user32
    user32.MessageBoxW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                   ctypes.c_wchar_p, ctypes.c_uint]
    user32.MessageBoxW.restype = ctypes.c_int
    answer = user32.MessageBoxW(
        None,
        f'Install Dirt Gear for this Windows account?\n\nLocation:\n{target}\n\nNo administrator access is needed.',
        TITLE, 0x00000004 | 0x00000020 | 0x00010000,
    )
    if answer != 6:  # IDYES
        return True
    try:
        install(target, make_shortcuts=make_shortcuts)
    except Exception as error:
        user32.MessageBoxW(None, f'Dirt Gear could not be installed.\n\n{error}',
                           TITLE, 0x00000010 | 0x00010000)
        return False
    user32.MessageBoxW(None, 'Dirt Gear is installed. Open it from your Desktop or Start menu.',
                       TITLE, 0x00000040 | 0x00010000)
    return True


def wait_for_process(pid: int, timeout_ms: int = 60000) -> None:
    """Wait until the Dirt Gear process that started this update has exited."""
    if os.name != 'nt' or pid <= 0:
        return
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if handle:
        kernel32.WaitForSingleObject(handle, timeout_ms)
        kernel32.CloseHandle(handle)
    time.sleep(1)


def run_update(target: Path, pid: int, launch: bool = True) -> None:
    """Silent in-place update started by the app; reopens Dirt Gear afterwards."""
    wait_for_process(pid)
    try:
        executable = install(target, make_shortcuts=False)
        refresh_shortcuts(executable)
        refresh_icons()
    except Exception as error:
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, f'Dirt Gear could not be updated.\n\n{error}\n\n'
                                             'Your previous version is still installed.', TITLE, 0x00000010 | 0x00010000)
        raise SystemExit(1)
    if launch:
        subprocess.Popen([str(executable)], cwd=str(executable.parent),
                         creationflags=0x00000008 | 0x00000200, close_fds=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--quiet', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--no-shortcuts', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--update', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--wait-pid', type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument('--no-launch', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    target = args.target or Path(os.environ['LOCALAPPDATA']) / 'Programs/Dirt Gear'
    if args.update:
        run_update(target, args.wait_pid, launch=not args.no_launch)
    elif args.quiet:
        print(install(target, make_shortcuts=not args.no_shortcuts))
    else:
        if not show_installer(target, make_shortcuts=not args.no_shortcuts):
            raise SystemExit(1)


if __name__ == '__main__':
    main()

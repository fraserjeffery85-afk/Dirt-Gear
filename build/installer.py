"""Single-file per-user installer for Dirt Gear."""
from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from zipfile import ZipFile


APP_NAME = 'Dirt Gear'


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
            target.rename(backup)
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
        'Dirt Gear v1.0 Setup', 0x00000004 | 0x00000020 | 0x00010000,
    )
    if answer != 6:  # IDYES
        return True
    try:
        install(target, make_shortcuts=make_shortcuts)
    except Exception as error:
        user32.MessageBoxW(None, f'Dirt Gear could not be installed.\n\n{error}',
                           'Dirt Gear v1.0 Setup', 0x00000010 | 0x00010000)
        return False
    user32.MessageBoxW(None, 'Dirt Gear is installed. Open it from your Desktop or Start menu.',
                       'Dirt Gear v1.0 Setup', 0x00000040 | 0x00010000)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--quiet', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--no-shortcuts', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    target = args.target or Path(os.environ['LOCALAPPDATA']) / 'Programs/Dirt Gear'
    if args.quiet:
        print(install(target, make_shortcuts=not args.no_shortcuts))
    else:
        if not show_installer(target, make_shortcuts=not args.no_shortcuts):
            raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Create the redistributable Dirt Gear program payload (dist/Dirt Gear -> build/payload.zip)."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'dist/Dirt Gear'
OUTPUT = ROOT / 'build/payload.zip'

with ZipFile(OUTPUT, 'w', compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
    for path in sorted(BUILD.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(BUILD)
        if any(part.lower() in ('tests', '__pycache__') for part in relative.parts):
            continue
        archive.write(path, relative.as_posix())
    for doc in ('README.md', 'VERSION.txt', 'CHANGELOG.md', 'THIRD_PARTY_NOTICES.txt'):
        if (ROOT / doc).is_file():
            archive.write(ROOT / doc, doc)

with ZipFile(OUTPUT) as archive:
    assert archive.getinfo('Dirt Gear.exe').file_size > 1_000_000
    assert archive.getinfo('_internal/static/app.js').file_size > 1000
    assert archive.getinfo('_internal/static/brand.ttf').file_size > 1000
    assert archive.getinfo('_internal/VERSION.txt').file_size > 0
    assert archive.getinfo('_internal/update_public_key.pem').file_size > 0
    assert not any(name.lower().endswith('signing-key.pem') for name in archive.namelist())
    assert not any(name.lower().endswith(('.psd', '.dirtgear', '.motogear', '.tga', '.pnt')) for name in archive.namelist())
    print(f'Payload: {len(archive.namelist())} files, {OUTPUT.stat().st_size / 1024 / 1024:.1f} MiB')

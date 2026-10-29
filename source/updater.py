"""Dirt Gear update checks — the same approach as Optic and Moto Lines Studio.

On start the app asks GitHub for the latest release of the repository built
into the release (update_repo.txt, written by the release workflow). Local or
unofficial builds have no repository and never check.

A release carries the installer plus `update.json` (version, installer name,
size, SHA-256) and `update.json.sig` (base64 Ed25519 signature of the exact
update.json bytes). The app installs only when the signature matches the
public key built into it and the download matches the size and SHA-256.
Releases published before the signing key secret is set have no signature:
the app still announces them but only offers to open the download page.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API = os.environ.get('DIRT_GEAR_UPDATE_API', 'https://api.github.com')
USER_AGENT = 'Dirt-Gear-Updater'
TIMEOUT = 10
MAX_INSTALLER = 400 * 1024 * 1024


def _root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent))


def _read(name: str) -> str:
    for folder in (_root(), _root().parent):
        path = folder / name
        if path.is_file():
            return path.read_text(encoding='utf-8').strip()
    return ''


def app_version() -> str:
    return _read('VERSION.txt') or '0.0.0'


def update_repo() -> str:
    repo = _read('update_repo.txt')
    return repo if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo or '') else ''


def parse_version(text: str) -> tuple[int, ...]:
    match = re.match(r'v?(\d+(?:\.\d+)*)', (text or '').strip())
    if not match:
        return (0,)
    parts = [int(p) for p in match.group(1).split('.')]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _get(url: str, limit: int = 2 * 1024 * 1024) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT,
                                                   'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Update information is unexpectedly large.')
    return data


def public_key():
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    pem = _read('update_public_key.pem')
    return load_pem_public_key(pem.encode()) if pem else None


def verify(manifest: bytes, signature_b64: bytes) -> bool:
    key = public_key()
    if key is None:
        return False
    try:
        key.verify(base64.b64decode(signature_b64.strip(), validate=True), manifest)
        return True
    except Exception:
        return False


def release_notes(body: str) -> str:
    body = (body or '').strip()
    return body[:4000]


def check() -> dict:
    """Ask GitHub for the latest release. Never raises for network problems."""
    current = app_version()
    repo = update_repo()
    result = {'enabled': bool(repo), 'current': current, 'available': False}
    if not repo:
        return result
    try:
        release = json.loads(_get(f'{API}/repos/{repo}/releases/latest'))
    except Exception as exc:
        return result | {'error': f'Could not reach GitHub ({exc.__class__.__name__}).'}
    latest = str(release.get('tag_name', '')).lstrip('v')
    result |= {'latest': latest, 'page': release.get('html_url', ''),
               'notes': release_notes(release.get('body', ''))}
    if not latest or not is_newer(latest, current):
        return result
    result['available'] = True
    assets = {a.get('name'): a for a in release.get('assets', [])}
    manifest_asset, signature_asset = assets.get('update.json'), assets.get('update.json.sig')
    result['signed'] = False
    if manifest_asset and signature_asset:
        try:
            manifest_bytes = _get(manifest_asset['browser_download_url'], 64 * 1024)
            signature = _get(signature_asset['browser_download_url'], 4 * 1024)
            if verify(manifest_bytes, signature):
                manifest = json.loads(manifest_bytes)
                installer = assets.get(manifest.get('file'))
                if (str(manifest.get('version')) == latest and installer and
                        re.fullmatch(r'[0-9a-f]{64}', str(manifest.get('sha256', ''))) and
                        0 < int(manifest.get('size', 0)) <= MAX_INSTALLER):
                    result['signed'] = True
                    result['installer'] = {'url': installer['browser_download_url'],
                                           'name': manifest['file'], 'size': int(manifest['size']),
                                           'sha256': manifest['sha256']}
        except Exception:
            result['signed'] = False
    return result


def download(info: dict, folder: Path, progress=None) -> Path:
    """Download the verified installer; check size and SHA-256 before returning it."""
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[^A-Za-z0-9._-]', '_', info['name'])
    if not name.lower().endswith('.exe'):
        raise ValueError('Unexpected update file.')
    destination = folder / name
    temporary = destination.with_suffix('.part')
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(info['url'], headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > info['size']:
                    raise ValueError('The update download is larger than expected.')
                digest.update(chunk)
                out.write(chunk)
                if progress:
                    progress(size, info['size'])
        if size != info['size'] or digest.hexdigest() != info['sha256']:
            raise ValueError('The update download failed its integrity check, so it was not installed.')
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)

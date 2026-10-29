"""Updater tests against a fake GitHub API (no network needed).

Run: python tests/test_updater.py"""
import base64
import hashlib
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

FILES = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = FILES.get(self.path)
        if body is None:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{server.server_port}'

import os
os.environ['DIRT_GEAR_UPDATE_API'] = BASE
import updater  # noqa: E402

key = Ed25519PrivateKey.generate()
updater.public_key = lambda: key.public_key()
updater.update_repo = lambda: 'owner/Dirt-Gear'
updater.app_version = lambda: '1.0.1'


def publish(version, installer=b'MZ fake installer bytes' * 1000, sign=True, tamper_sig=False, manifest_version=None):
    FILES.clear()
    name = f'Dirt-Gear-Setup-{version}.exe'
    manifest = json.dumps({'version': manifest_version or version, 'file': name, 'size': len(installer),
                           'sha256': hashlib.sha256(installer).hexdigest()}).encode()
    assets = [{'name': name, 'browser_download_url': f'{BASE}/dl/{name}'},
              {'name': 'update.json', 'browser_download_url': f'{BASE}/dl/update.json'}]
    FILES[f'/dl/{name}'] = installer
    FILES['/dl/update.json'] = manifest
    if sign:
        signature = key.sign(manifest if not tamper_sig else manifest + b' ')
        FILES['/dl/update.json.sig'] = base64.b64encode(signature)
        assets.append({'name': 'update.json.sig', 'browser_download_url': f'{BASE}/dl/update.json.sig'})
    FILES['/repos/owner/Dirt-Gear/releases/latest'] = json.dumps({
        'tag_name': 'v' + version, 'html_url': f'https://github.com/owner/Dirt-Gear/releases/tag/v{version}',
        'body': '## ' + version + '\n- Faster', 'assets': assets}).encode()
    return installer


def ok(condition, message):
    if not condition:
        raise SystemExit('FAIL ' + message)
    print('PASS', message)


ok(updater.is_newer('1.0.2', '1.0.1') and updater.is_newer('v1.1', '1.0.9') and updater.is_newer('2.0.0', '1.10.3'),
   'newer versions detected (incl. v-prefix, 1.10 > 1.9 style)')
ok(not updater.is_newer('1.0.1', '1.0.1') and not updater.is_newer('1.0', '1.0.0') and not updater.is_newer('1.0.0', '1.0.1'),
   'same or older versions are not offered')

publish('1.0.2')
r = updater.check()
ok(r['available'] and r['signed'] and r['installer']['name'] == 'Dirt-Gear-Setup-1.0.2.exe', 'signed newer release offered for install')
ok(r['latest'] == '1.0.2' and 'Faster' in r['notes'], 'release notes come through')

with tempfile.TemporaryDirectory() as folder:
    path = updater.download(r['installer'], Path(folder))
    ok(path.is_file() and path.read_bytes() == FILES['/dl/Dirt-Gear-Setup-1.0.2.exe'], 'download verified by size and SHA-256')
    FILES['/dl/Dirt-Gear-Setup-1.0.2.exe'] = b'X' * r['installer']['size']   # swapped file, same size
    try:
        updater.download(r['installer'], Path(folder) / 'b')
        ok(False, 'tampered download rejected')
    except ValueError:
        ok(not any((Path(folder) / 'b').glob('*.exe')), 'tampered download rejected and removed')

publish('1.0.2', tamper_sig=True)
r = updater.check()
ok(r['available'] and not r['signed'] and 'installer' not in r, 'bad signature: announced but never installable')

publish('1.0.2', sign=False)
r = updater.check()
ok(r['available'] and not r['signed'] and r['page'].startswith('https://github.com/'), 'unsigned release: offers the download page')

publish('1.0.2', manifest_version='1.0.9')
r = updater.check()
ok(not r['signed'], 'manifest for a different version is refused')

publish('1.0.1')
ok(not updater.check()['available'], 'current version: nothing offered')

FILES.clear()
r = updater.check()
ok(r['enabled'] and not r['available'] and 'error' in r, 'GitHub unreachable or no release: no crash, no offer')

updater.update_repo = lambda: ''
ok(updater.check() == {'enabled': False, 'current': '1.0.1', 'available': False}, 'builds without a repository never check')

pem = (ROOT / 'source/update_public_key.pem').read_bytes()
ok(isinstance(load_pem_public_key(pem), Ed25519PublicKey), 'bundled public key is a valid Ed25519 key')
print('ALL UPDATER TESTS PASS')

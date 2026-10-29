"""Write update.json (+ update.json.sig when a signing key is available).

Usage: python tools/make_update.py <installer.exe> <version> <out dir>
The private key is read from the UPDATE_SIGNING_KEY environment variable
(the repository secret). Without it only update.json is written, and the app
announces the release but sends people to the download page."""
import base64, hashlib, json, os, sys
from pathlib import Path

installer, version, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
data = installer.read_bytes()
manifest = json.dumps({'version': version, 'file': installer.name, 'size': len(data),
                       'sha256': hashlib.sha256(data).hexdigest()}, indent=1).encode()
out.mkdir(parents=True, exist_ok=True)
(out / 'update.json').write_bytes(manifest)
pem = os.environ.get('UPDATE_SIGNING_KEY', '').strip()
if pem:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    key = load_pem_private_key(pem.encode(), password=None)
    (out / 'update.json.sig').write_text(base64.b64encode(key.sign(manifest)).decode())
    # Check it against the public key that ships in the app.
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    public = load_pem_public_key((Path(__file__).resolve().parents[1] / 'source/update_public_key.pem').read_bytes())
    public.verify(key.sign(manifest), manifest)
    print('Signed update.json')
else:
    print('UPDATE_SIGNING_KEY not set: update.json written unsigned (app will offer the download page).')

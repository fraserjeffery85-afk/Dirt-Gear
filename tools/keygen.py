"""Create a new Ed25519 update signing key pair for Dirt Gear.

Writes dirt-gear-update-signing-key.pem (private - add it as the
UPDATE_SIGNING_KEY repository secret, keep a safe offline copy, never commit)
and source/update_public_key.pem (public - built into the app).
Only needed once; a new key means everyone installs one release by hand."""
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

root = Path(__file__).resolve().parents[1]
key = Ed25519PrivateKey.generate()
private = root / 'dirt-gear-update-signing-key.pem'
private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
(root / 'source/update_public_key.pem').write_bytes(key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
print('Wrote', private, 'and source/update_public_key.pem')

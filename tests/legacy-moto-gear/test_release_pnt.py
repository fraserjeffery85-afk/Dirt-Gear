import hashlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
from PIL import Image
import app
from packing import pack_pnt, read_pnt

psd = Path("N:/RIDER GEAR PSD's/Rider Gear/FOX/2027/2027-Fox-360-Temper-By-Cquatty-and-KD/2027 Fox 360 Temper By Cquatty and KD.psd")
doc = app.Document(psd, psd.name)
textures = doc.textures()
assert set(textures) == {'rider', 'rider_n', 'rider_r'}
for stem, data in textures.items():
    image = Image.open(io.BytesIO(data))
    assert image.size == (4096, 4096)
    assert data[16] == (24 if stem == 'rider' else 32)
    if stem != 'rider':
        assert image.getchannel('A').getextrema() == (0, 0), stem

packed = pack_pnt('Moto Gear release test', textures)
entries = read_pnt(packed)
assert set(entries) == set(textures)
for stem, entry in entries.items():
    assert entry['size'] == (4096, 4096)
    assert entry['md5'] == hashlib.md5(textures[stem]).digest()
    if stem != 'rider':
        assert not any(entry['rgba'][3::4]), stem
print('Real 4K PSD: valid PNT with 24-bit Default and black-alpha 32-bit Norm/Spec: PASS')

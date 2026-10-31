"""Colour overlay tests (solid, gradient, strength, legacy tint, export, preview).
Run: python tests/test_overlay.py   (needs psd-tools 1.19)"""
import io, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
import app  # noqa: E402

def ok(c, m):
    if not c:
        raise SystemExit('FAIL ' + m)
    print('PASS', m)

logo = Image.new('RGBA', (200, 100), (0, 0, 0, 0))
logo.paste((220, 30, 30, 255), (20, 20, 180, 80))           # red bar with transparent border
a = np.asarray(app.apply_overlay(logo, {'mode': 'solid', 'color': '#00FF00', 'strength': 1}))
ok(tuple(a[50, 100]) == (0, 255, 0, 255) and a[5, 5, 3] == 0, 'solid overlay recolours the logo and keeps transparency')
h = np.asarray(app.apply_overlay(logo, {'mode': 'solid', 'color': '#0000FF', 'strength': 0.5}))
ok(abs(int(h[50, 100, 0]) - 110) <= 1 and abs(int(h[50, 100, 2]) - 142) <= 1, 'strength 50% blends original and overlay')
g = np.asarray(app.apply_overlay(logo, {'mode': 'gradient', 'start': '#FF0000', 'end': '#0000FF', 'angle': 0, 'strength': 1}))
ok(g[50, 25, 0] > g[50, 175, 0] and g[50, 175, 2] > g[50, 25, 2], 'gradient runs left (start) to right (end)')
v = np.asarray(app.apply_overlay(logo, {'mode': 'gradient', 'start': '#FF0000', 'end': '#0000FF', 'angle': 90, 'strength': 1}))
ok(v[25, 100, 0] > v[75, 100, 0], 'top-to-bottom direction works')
ok(app.artwork_overlay({'color': '#123456'}) == {'mode': 'solid', 'color': '#123456', 'strength': 1}, 'old single-colour tints still work')
for bad in ({'mode': 'neon'}, {'mode': 'solid', 'color': 'red'}, {'mode': 'gradient', 'start': '#000000', 'end': '#FFFFFF', 'strength': 2}):
    try:
        app.validate_overlay(bad); ok(False, 'reject %r' % bad)
    except ValueError:
        pass
ok(True, 'invalid overlays rejected')

with tempfile.TemporaryDirectory() as tmp:
    psd = Path(tmp) / 'like-user.psd'
    subprocess.run([sys.executable, str(ROOT / 'tests/make_like_user_psd.py'), str(psd)], check=True)
    doc = app.Document(psd, 'like-user.psd')
    buf = io.BytesIO(); logo.save(buf, 'PNG')
    key = 'logo1'; doc.assets[key] = {'name': 'Logo', 'image': logo}
    art = {'id': 'a', 'asset': key, 'name': 'Logo', 'x': 512, 'y': 400, 'width': 400, 'height': 200, 'rotation': 0, 'opacity': 1, 'visible': True,
           'overlay': {'mode': 'solid', 'color': '#00FF00', 'strength': 1}}
    doc.update({'artworks': [art], 'placement': ''})              # on top, so colour is unshaded
    full = doc.art_image()
    px = full.getpixel((512, 400))
    ok(px[:3] == (0, 255, 0), 'export artwork layer uses the overlay colour')
    doc.update({'placement': doc.state['shading']})
    fast = doc.fast_composite(True, 512)
    exact = doc.composite_default(True).resize(fast.size, Image.Resampling.BOX)
    d = np.abs(np.asarray(fast, dtype=np.int16) - np.asarray(exact, dtype=np.int16)).mean()
    ok(d < 3, f'fast preview matches exact render with a solid overlay under the shading (mean diff {d:.2f})')
    art['overlay'] = {'mode': 'gradient', 'start': '#FF00FF', 'end': '#00FFFF', 'angle': 45, 'strength': 0.8}
    doc.update({'artworks': [art]})
    fast = doc.fast_composite(True, 512)
    exact = doc.composite_default(True).resize(fast.size, Image.Resampling.BOX)
    d = np.abs(np.asarray(fast, dtype=np.int16) - np.asarray(exact, dtype=np.int16)).mean()
    ok(d < 3, f'fast preview matches exact render with a gradient overlay (mean diff {d:.2f})')
    textures = doc.textures()
    ok(Image.open(io.BytesIO(textures['rider'])).mode == 'RGB', 'export still produces the RGB diffuse texture')
print('ALL OVERLAY TESTS PASS')

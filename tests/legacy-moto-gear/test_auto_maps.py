import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
import app

def make(with_spec):
    psd = PSDImage.new('RGB', (24, 24), color=(255, 255, 255))
    PixelLayer.frompil(Image.new('RGB', (24, 24), 'white'), psd, 'Base')
    PixelLayer.frompil(Image.new('RGBA', (24, 24), (128, 128, 128, 120)), psd, 'Shading')
    normals = Group.new(psd, 'Norms')
    PixelLayer.frompil(Image.new('RGBA', (24, 24), (128, 128, 255, 255)), normals, 'Panel A')
    PixelLayer.frompil(Image.new('RGBA', (8, 8), (200, 120, 220, 255)), normals, 'Panel B')
    normals.visible = False
    if with_spec:
        specs = Group.new(psd, 'Spec Reflection')
        PixelLayer.frompil(Image.new('RGB', (24, 24), (35, 35, 35)), specs, 'Reflection fill')
        specs.visible = False
    path = Path('work/test-auto-spec.psd' if with_spec else 'work/test-no-spec.psd')
    psd.save(path)
    return app.Document(path, path.name)

for with_spec in (False, True):
    doc = make(with_spec)
    assert len(doc.state['normal_layers']) == 2
    assert bool(doc.state['spec']) == with_spec
    assert doc.state['shading']
    doc.prepare_preview()
    textures = doc.textures()
    normal = Image.open(io.BytesIO(textures['rider_n']))
    spec = Image.open(io.BytesIO(textures['rider_r']))
    assert normal.getchannel('A').getextrema() == (0, 0)
    assert spec.getchannel('A').getextrema() == (0, 0)
    assert normal.getpixel((20, 20))[:3] == (128, 128, 255)
    if not with_spec:
        assert spec.convert('RGB').getextrema() == ((0, 0), (0, 0), (0, 0))
    else:
        assert spec.getpixel((20, 20))[:3] == (35, 35, 35)
print('Auto Norm/Spec groups and generated black Spec, with black alpha: PASS')

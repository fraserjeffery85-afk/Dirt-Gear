import sys
from pathlib import Path
sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import BlendMode
import app

psd = PSDImage.new('RGB', (32, 32), color=(255, 255, 255))
PixelLayer.frompil(Image.new('RGB', (32, 32), 'white'), psd, 'Base')
shade = PixelLayer.frompil(Image.new('RGBA', (32, 32), (128, 128, 128, 255)), psd, 'Shading')
shade.blend_mode = BlendMode.MULTIPLY
n1 = PixelLayer.frompil(Image.new('RGBA', (32, 32), (128, 128, 255, 255)), psd, 'Normal A')
n2 = PixelLayer.frompil(Image.new('RGBA', (16, 16), (255, 128, 128, 255)), psd, 'Normal B')
n1.visible = n2.visible = False
s = PixelLayer.frompil(Image.new('RGB', (32, 32), (20, 20, 20)), psd, 'Spec')
s.visible = False
path = Path('work/test-revised.psd')
psd.save(path)
doc = app.Document(path, path.name)
assert len(doc.state['normal_layers']) == 2
doc.prepare_preview()
assert set(doc.previews) == {'default'}
normal = doc.isolated('normal')
assert normal.size == (32, 32)
assert normal.getpixel((1, 1))[:3] == (255, 128, 128)
assert normal.getpixel((30, 30))[:3] == (128, 128, 255)
art = Image.new('RGBA', (8, 8), (1, 2, 3, 255))
doc.assets['a'] = {'name': 'Logo', 'image': art}
doc.state['artworks'] = [{'id': 'a', 'asset': 'a', 'name': 'Logo', 'x': 16, 'y': 16,
                         'width': 8, 'height': 8, 'rotation': 0, 'opacity': 1,
                         'visible': True, 'color': '#E9FF57'}]
result = doc.composite_default()
assert result.getpixel((16, 16)) == (116, 128, 43)
assert len(doc.psd) == 5
print('Multiple Norm layers, lazy map previews, artwork colour and PSD cleanup: PASS')

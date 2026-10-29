import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import BlendMode
import app

path = Path('work/placement-test.psd')
psd = PSDImage.new('RGB', (64, 64), color=(255, 255, 255))
PixelLayer.frompil(Image.new('RGB', (64, 64), 'white'), psd, 'Base')
PixelLayer.frompil(Image.new('RGBA', (64, 64), (0, 0, 255, 255)), psd, 'Design')
shade = PixelLayer.frompil(Image.new('RGBA', (64, 64), (128, 128, 128, 255)), psd, 'Shading')
shade.blend_mode = BlendMode.MULTIPLY
normal = PixelLayer.frompil(Image.new('RGB', (64, 64), (128, 128, 255)), psd, 'Normal')
normal.visible = False
psd.save(path)
doc = app.Document(path, path.name)
doc.assets['logo'] = {'name': 'Logo', 'image': Image.new('RGBA', (20, 20), (255, 0, 0, 255))}
doc.state['artworks'] = [{'id': 'a', 'asset': 'logo', 'name': 'Logo', 'x': 32, 'y': 32,
                          'width': 20, 'height': 20, 'rotation': 0, 'opacity': 1, 'visible': True}]
assert doc.composite_default().getpixel((32, 32)) == (128, 0, 0)
design_id = next(r['id'] for r in doc.rows if r['name'] == 'Design')
doc.update({**doc.state, 'placement': design_id})
assert doc.composite_default().getpixel((32, 32)) == (0, 0, 128)
assert Image.open(io.BytesIO(doc.textures()['rider'])).getpixel((32, 32)) == (0, 0, 128)
normal_id = doc.state['normal']
try:
    doc.update({**doc.state, 'placement': normal_id})
    raise AssertionError('Norm placement should be rejected')
except ValueError:
    pass
app.DOC = doc
client = app.app.test_client()
response = client.get('/api/layer/thumbnail/'+design_id, headers={'X-Moto-Token': app.TOKEN})
assert response.status_code == 200 and Image.open(io.BytesIO(response.data)).size == (36, 36)
print('Dragging artwork placement changes the export, protects Norm, and layer preview loads: PASS')

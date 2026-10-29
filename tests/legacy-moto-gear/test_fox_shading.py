import sys
from pathlib import Path

sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
from PIL import Image
import app

psd = Path("N:/RIDER GEAR PSD's/Rider Gear/FOX/2027/2027-Fox-360-Temper-By-Cquatty-and-KD/2027 Fox 360 Temper By Cquatty and KD.psd")
doc = app.Document(psd, psd.name)
assert doc.state['shading'] == doc.state['placement']
assert doc.layers[doc.state['shading']].name == 'Shading'
doc.assets['red'] = {'name': 'Red test', 'image': Image.new('RGBA', (800, 800), (255, 0, 0, 255))}
doc.state['artworks'] = [{'id': 'red', 'asset': 'red', 'name': 'Red test', 'x': 2200, 'y': 1700,
                          'width': 800, 'height': 800, 'rotation': 0, 'opacity': 1, 'visible': True}]
under = doc.composite_default().getpixel((2200, 1700))
doc.state['placement'] = '4'  # Above the Shading group; hidden UV layer is only an anchor.
above = doc.composite_default().getpixel((2200, 1700))
assert under[0] < above[0] and above == (255, 0, 0), (under, above)
print('Real Fox PSD: artwork below Shading is darkened in the export:', under, 'vs above:', above)

import sys
from pathlib import Path
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
import app

psd = PSDImage.new('RGB', (1024, 1024), color=(255, 255, 255))
PixelLayer.frompil(Image.new('RGB', (1024, 1024), 'white'), psd, 'Base')
path = Path('work/test-text-quality.psd')
psd.save(path)
doc = app.Document(path, path.name)
app.DOC = doc
doc.prepare_preview()
client = app.app.test_client()
full = client.get('/api/preview/default?full=1', headers={'X-Moto-Token':app.TOKEN})
assert full.status_code == 200
import io
assert Image.open(io.BytesIO(full.data)).size == (1024, 1024)
font = next(f for f in app.installed_fonts().values() if f['byd'])
settings = {'value':'TIPENE','font':font['id'],'size':80,'fill':'#071F65','stroke':0,'outline':'#000000'}
response = client.post('/api/text', json=settings, headers={'X-Moto-Token':app.TOKEN})
assert response.status_code == 200, response.data
item = response.get_json()
stored = doc.assets[item['id']]['image']
assert stored.width > item['width'] and stored.height > item['height']
art = {'id':'a','asset':item['id'],'name':'TIPENE','x':512,'y':512,'width':item['width']*5,
       'height':item['height']*5,'rotation':0,'opacity':1,'visible':True,'text':item['text']}
doc.state['artworks'] = [art]
scales = []
original = app.render_text_bitmap
def watched(settings, scale=1):
    scales.append(scale)
    return original(settings, scale)
app.render_text_bitmap = watched
try:
    rendered = doc.art_image()
finally:
    app.render_text_bitmap = original
assert scales and max(scales) > 1
assert rendered.getchannel('A').getbbox()
print('Text keeps logical dimensions, stores a sharp preview, and rerenders for 4K stretching: PASS')

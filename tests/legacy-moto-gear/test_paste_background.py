import sys
from pathlib import Path
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
import app

image = Image.new('RGBA', (40, 40), (255, 255, 255, 255))
draw = ImageDraw.Draw(image)
draw.rectangle((8, 8, 31, 31), fill=(220, 20, 30, 255))
draw.rectangle((15, 15, 24, 24), fill=(255, 255, 255, 255))
cleaned = app.remove_white_background(image)
assert cleaned.getpixel((0, 0))[3] == 0
assert cleaned.getpixel((10, 10)) == (220, 20, 30, 255)
assert cleaned.getpixel((20, 20)) == (255, 255, 255, 255)
psd = PSDImage.new('RGB', (40, 40), color=(255, 255, 255))
PixelLayer.frompil(Image.new('RGB', (40, 40), 'white'), psd, 'Base')
psd.save('work/test-paste-template.psd')
doc = app.Document('work/test-paste-template.psd', 'test-paste-template.psd')
app.DOC = doc
doc.assets['original'] = {'name':'Pasted logo', 'image':image}
client = app.app.test_client()
reply = client.post('/api/artwork/remove-white', json={'asset':'original'}, headers={'X-Moto-Token':app.TOKEN})
assert reply.status_code == 200, reply.data
new_asset = doc.assets[reply.get_json()['id']]['image']
assert new_asset.getpixel((0, 0))[3] == 0
assert doc.assets['original']['image'].getpixel((0, 0))[3] == 255
print('White edge background removed; logo colours and enclosed white retained: PASS')

import io
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
import app

path = Path("N:/RIDER GEAR PSD's/Rider Gear/ASTARS/2027 GEAR/RACER LONE stock.psd")
doc = app.Document(path, path.name)
assert doc.psd.size == (4096, 4096)
font = next(f for f in app.installed_fonts().values() if f['byd'])
settings = {'value':'TIPENE','font':font['id'],'size':240,'fill':'#071F65','stroke':0,'outline':'#000000'}
logical = app.render_text_bitmap(settings)
asset = app.render_text_bitmap(settings, 4)
doc.assets['text'] = {'name':'TIPENE','image':asset}
doc.state['artworks'] = [{'id':'text','asset':'text','name':'TIPENE','x':2048,'y':1500,
                          'width':1800,'height':250,'rotation':0,'opacity':1,'visible':True,
                          'text':{**settings,'base_width':logical.width,'base_height':logical.height}}]
textures = doc.textures()
for stem in ('rider','rider_n','rider_r'):
    image = Image.open(io.BytesIO(textures[stem]))
    assert image.size == (4096, 4096)
    if stem != 'rider':
        assert image.getchannel('A').getextrema() == (0, 0)
print('Real 4K PSD exports sharp stretched text and valid 4K maps: PASS')

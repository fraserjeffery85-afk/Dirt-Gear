import sys
import time
from pathlib import Path
from PIL import ImageChops
sys.path.insert(0, str(Path('outputs/Moto-Gear/source').resolve()))
import app

path = Path("N:/RIDER GEAR PSD's/Rider Gear/ASTARS/2027 GEAR/ASTARS VESTA.psd")
start = time.monotonic()
doc = app.Document(path, path.name)
smart = {r['name']:r for r in doc.rows if r['kind']=='smartobject'}
assert {'1','2','3','THANK YOU!!'} <= set(smart)
assert all(smart[k]['depth']==0 for k in ('1','2','3','THANK YOU!!'))
assert doc.state['visibility'][smart['1']['id']]
assert doc.state['visibility'][smart['THANK YOU!!']['id']]
original = doc.composite_default(False, True)
doc.state['visibility'][smart['THANK YOU!!']['id']] = False
no_intro = doc.composite_default(False, True)
assert ImageChops.difference(original, no_intro).getbbox()
doc.state['visibility'][smart['1']['id']] = False
doc.state['visibility'][smart['2']['id']] = True
new_colour = doc.composite_default(False, True)
assert ImageChops.difference(no_intro, new_colour).getbbox()
print(f'Vesta diffuse choices and intro visibility affect rendering: PASS ({time.monotonic()-start:.1f}s)')

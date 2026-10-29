import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path('outputs/Moto-Gear/source').resolve()))
import app
from PIL import Image,ImageChops
psd=Path("N:/RIDER GEAR PSD's/Rider Gear/FOX/2027/2027-Fox-360-Temper-By-Cquatty-and-KD/2027 Fox 360 Temper By Cquatty and KD.psd")
doc=app.Document(psd,psd.name);doc.prepare_preview()
doc.assets['red']={'name':'red','image':Image.new('RGBA',(600,300),'red')}
doc.state['artworks']=[{'id':'red','asset':'red','name':'red','x':2200,'y':1700,'width':600,'height':300,'rotation':20,'opacity':1,'visible':True}]
t=time.perf_counter();fast=doc.composite_default();a=time.perf_counter()-t
doc.render_key=None;doc.base_render_key=None
t=time.perf_counter();full=doc.composite_default();b=time.perf_counter()-t
assert ImageChops.difference(fast,full).getbbox() is None,'Region rendering differs from full PSD composite'
Path('work/v11-performance.json').write_text(json.dumps({'region_seconds':a,'full_seconds':b,'exact_match':True,'cache_mb':doc.pixel_cache_bytes/1024**2}))
print('EXACT MATCH region',a,'full',b,flush=True)

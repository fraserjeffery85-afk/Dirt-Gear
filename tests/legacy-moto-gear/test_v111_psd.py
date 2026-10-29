import sys,time
from pathlib import Path
sys.path.insert(0,str(Path('outputs/Moto-Gear/source').resolve()))
import app
p=Path("N:/RIDER GEAR PSD's/Rider Gear/FOX/2026 FOX FLEXAIR DNGR ST LOUIS BY RC.psd")
d=app.Document(p,p.name)
print('NORMALS',[(k,d.layers[k].name) for k in d.state['normal_layers']],flush=True)
assert d.state['normal_layers']==['4.2.0']
assert all('NORM'==d.layers[k].parent.name for k in d.state['normal_layers'])
d.update(d.state);d.prepare_preview();print('OPENED',d.psd.size,flush=True)
textures=d.textures()
from PIL import Image
import io
for key in ('rider_n','rider_r'):assert Image.open(io.BytesIO(textures[key])).getchannel('A').getextrema()==(0,0)
print('PASS real failing PSD loads, correct Norm descendants, exported black map alphas',flush=True)


import sys,io,os,tempfile
from pathlib import Path
sys.path.insert(0,str(Path('outputs/Moto-Gear/source').resolve()))
import app
from PIL import Image,ImageChops
import numpy as np
os.environ['LOCALAPPDATA']=str(Path('work/v11-test-profile').resolve())
doc=app.Document('work/test-template.psd','sample.psd');app.DOC=doc;doc.prepare_preview()
client=app.app.test_client();headers={'X-Moto-Token':app.TOKEN}
font=next(f for f in app.installed_fonts() if 'byd-name-font-stock' in f.lower())
s={'value':'TEST','font':font,'size':100,'stroke':3,'outline':'#000000','fill':'#ffffff','gradient':{'start':'#ff0000','end':'#0000ff','angle':90}}
r=client.post('/api/text',json=s,headers=headers);assert r.status_code==200,r.json
asset=r.json;im=doc.assets[asset['id']]['image'];pixels=np.array(im);opaque=pixels[pixels[:,:,3]>200];assert opaque[:,0].max()>150 and opaque[:,2].max()>150
art={'id':'test','asset':asset['id'],'name':'TEST','x':64,'y':64,'width':80,'height':30,'opacity':1,'rotation':15,'visible':True,'text':asset['text']};doc.state['artworks']=[art]
fast=doc.composite_default();doc.base_render_key=None;doc.render_key=None;full=doc.composite_default();assert ImageChops.difference(fast,full).getbbox() is None
packed=app.project_bytes(doc);restored=app.load_project(io.BytesIO(packed));assert restored.state['artworks'][0]['text']['gradient']==s['gradient']
assert client.post('/api/sample-colour',json={'x':10,'y':10},headers=headers).status_code==200
for channel in ('color','shape'):
 layer=next(l for l in doc.layers.values() if l.kind=='pixel');a=layer.numpy(channel)
 if a is not None:
  expected=a.copy();a[:]=0;assert np.array_equal(layer.numpy(channel),expected),'cached pixel mutation'
print('PASS gradient bitmap, editable project roundtrip, exact region composite, colour sample, cache isolation')

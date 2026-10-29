import json,urllib.request,sys,time,io
from pathlib import Path
from PIL import Image
import numpy as np
SP=Path(sys.argv[1]);psdfile=sys.argv[2]
c=json.loads((SP/'session.json').read_text());base=c['url'].split('/?')[0];tok=c['token']
def raw(path,data=None,method=None,ct='application/json'):
    body=json.dumps(data).encode() if data is not None and ct=='application/json' else data
    return urllib.request.urlopen(urllib.request.Request(base+'/api/'+path,data=body,method=method,headers={'X-Dirt-Token':tok,'Content-Type':ct}),timeout=600)
def req(*a,**k): return json.load(raw(*a,**k))
b='B';content=Path(psdfile).read_bytes()
body=(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="x.psd"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+content+f'\r\n--{b}--\r\n'.encode())
t=time.time();doc=req('open',body,ct='multipart/form-data; boundary='+b);print('open',round(time.time()-t,2),'shading=',doc['state']['shading'],'placement=',doc['state']['placement'])
st=doc['state']
t=time.time();req('setup',st);print('first preview (setup)',round(time.time()-t,2))
t=time.time();n=0
for l in doc['layers'][:30]: raw('layer/thumbnail/'+l['id']).read();n+=1
print(f'{n} thumbnails',round(time.time()-t,2))
# toggle a visible non-map layer off
cand=[l for l in doc['layers'] if not l['group'] and st['visibility'][l['id']] and l['id'] not in st['normal_layers'] and l['id']!=st['shading']]
st['visibility'][cand[len(cand)//2]['id']]=False
t=time.time();req('setup',st);print('toggle',round(time.time()-t,2))
st['visibility'][cand[len(cand)//2]['id']]=True
t=time.time();req('setup',st);print('toggle back (cached)',round(time.time()-t,2))
# artwork: big white text block
fonts=req('fonts');font=next(f['id'] for f in fonts if 'byd-number-font-race' in f['id'].lower())
txt=req('text',{'value':'76','font':font,'size':400,'fill':'#ffffff','stroke':0,'outline':'#000000','gradient':None})
W,H=doc['width'],doc['height']
st['artworks']=[{'id':'a','asset':txt['id'],'name':'76','x':W*0.5,'y':H*0.55,'width':W*0.4,'height':W*0.4*txt['height']/txt['width'],'rotation':0,'opacity':1,'visible':True,'text':txt['text']}]
t=time.time();live=Image.open(io.BytesIO(raw('render/live',st).read())).convert('RGB');print('live render with artwork',round(time.time()-t,2))
st['artworks'][0]['x']+=W*0.02
t=time.time();live=Image.open(io.BytesIO(raw('render/live',st).read())).convert('RGB');print('live render after move',round(time.time()-t,2))
if '--exact' in sys.argv:
    t=time.time();req('render',st);exact=Image.open(io.BytesIO(raw('preview/proof').read())).convert('RGB');print('exact render',round(time.time()-t,2))
    ref=exact.resize(live.size,Image.Resampling.BOX)
    d=np.abs(np.asarray(ref,dtype=np.int16)-np.asarray(live,dtype=np.int16))
    print(f'preview vs exact: mean {d.mean():.3f} p99 {np.percentile(d,99):.1f} max {d.max()}')
    live.save(str(psdfile)+'.live.png');ref.save(str(psdfile)+'.exact.png')

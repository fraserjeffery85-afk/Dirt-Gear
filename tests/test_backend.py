import json,urllib.request,io,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from packing import read_pnt
from PIL import Image
SP=Path(sys.argv[1]);c=json.loads((SP/'session.json').read_text());base=c['url'].split('/?')[0];tok=c['token']
def raw(path,data=None,method=None,ct='application/json'):
    body=json.dumps(data).encode() if data is not None and ct=='application/json' else data
    r=urllib.request.Request(base+'/api/'+path,data=body,method=method,headers={'X-Dirt-Token':tok,'Content-Type':ct})
    return urllib.request.urlopen(r,timeout=120)
def req(*a,**k): return json.load(raw(*a,**k))
def upload(path,file):
    b='DGBoundary';content=Path(file).read_bytes()
    body=(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{Path(file).name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+content+f'\r\n--{b}--\r\n'.encode())
    return req(path,body,ct='multipart/form-data; boundary='+b)
doc=upload('open',SP/'fixtures/test-gear.psd');state=doc['state']
fonts=req('fonts');font=next(f['id'] for f in fonts if 'byd-number-font-race' in f['id'].lower())
t=req('text',{'value':'76','font':font,'size':200,'fill':'#ffffff','stroke':4,'outline':'#000000','gradient':None})
state['artworks']=[{'id':'a1','asset':t['id'],'name':'76','x':700,'y':700,'width':t['width'],'height':t['height'],'rotation':10,'opacity':1,'visible':True,'text':t['text']}]
state['name']='Dirt Test'
req('setup',state)
pnt=raw('export/pnt',state).read();tex=read_pnt(pnt);print('pnt textures',{k:(v[0],v[1]) if isinstance(v,tuple) else type(v).__name__ for k,v in tex.items()})
z=zipfile.ZipFile(io.BytesIO(raw('export/tga',state).read()))
for n in z.namelist():
    im=Image.open(io.BytesIO(z.read(n)));print(n,im.mode,im.size,'alpha',im.getchannel('A').getextrema() if im.mode=='RGBA' else None)
    if n!='rider.tga': assert im.mode=='RGBA' and im.getchannel('A').getextrema()==(0,0)
    else: assert im.mode=='RGB'
print('pnt header name',pnt[4:104].rstrip(b'\0'))
qs=req('project/quick-save',state);print('quick-save',qs['saved'])
assert qs['saved'].endswith('.dirtgear')
rec=req('project/recent');print('recent',rec)
re=req('project/reopen',{'id':rec['projects'][0]['id']});assert re['state']['artworks'][0]['id']=='a1'
proj=raw('project/save',state).read();(SP/'legacy.motogear').write_bytes(proj)
d2=upload('project/open',SP/'legacy.motogear');assert d2['state']['name']=='Dirt Test'
root=Path(SP/'lad/Dirt Gear');print('library',sorted(p.name for p in root.iterdir()))
if (SP/'lad/Moto Gear').is_dir(): assert (root/'imported-from-moto-gear.txt').exists(), 'Moto Gear library was not copied'
print('ALL PASS')

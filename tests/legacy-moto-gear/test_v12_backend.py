import io,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path('outputs/Moto-Gear/source').resolve()))
import app
from PIL import Image
with tempfile.TemporaryDirectory() as tmp:
 os.environ['LOCALAPPDATA']=tmp
 d=app.Document('work/test-template.psd','Test.psd');app.DOC=d;d.prepare_preview();client=app.app.test_client();headers={'X-Moto-Token':app.TOKEN}
 d.assets['a']={'name':'test','image':Image.new('RGBA',(8,8),'red')}
 ids=[client.post('/api/logos',json={'asset':'a'},headers=headers).json['id'] for _ in range(2)]
 imported=client.post('/api/logos/'+ids[0]+'/add',json={},headers=headers).json
 assert client.delete('/api/logos/'+ids[0]).status_code==403
 assert client.delete('/api/logos/'+ids[0],headers=headers).status_code==200
 assert not (app.library_root()/(ids[0]+'.json')).exists() and not (app.library_root()/(ids[0]+'.png')).exists()
 assert (app.library_root()/(ids[1]+'.png')).exists() and imported['id'] in d.assets
 assert client.delete('/api/logos/not-a-logo',headers=headers).status_code==404
 for kind in ('normal','spec'):
  before=d.isolated(kind).convert('RGB').tobytes()
  r=client.get('/api/viewer/map/'+kind,headers=headers);assert r.status_code==200
  im=Image.open(io.BytesIO(r.data));assert im.mode=='RGB' and im.tobytes()==before
  tga=app.tga_bytes(d.isolated(kind),True);assert Image.open(io.BytesIO(tga)).getchannel('A').getextrema()==(0,0)
 d.state['normal_layers']=[];d.state['normal']='';d.state['spec']=''
 normal=Image.open(io.BytesIO(client.get('/api/viewer/map/normal',headers=headers).data));assert normal.getpixel((0,0))==(128,128,255)
 spec=Image.open(io.BytesIO(client.get('/api/viewer/map/spec',headers=headers).data));assert spec.getextrema()==((0,0),(0,0),(0,0))
 print('PASS paired-file deletion, duplicate and project preservation, access checks, original map RGB, black export alpha, missing-map fallbacks')

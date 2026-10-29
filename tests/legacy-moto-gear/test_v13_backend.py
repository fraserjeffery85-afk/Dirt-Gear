import sys,os,tempfile,io
from pathlib import Path
sys.path.insert(0,str(Path('outputs/Moto-Gear/source').resolve()))
import app
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
with tempfile.TemporaryDirectory() as tmp:
 os.environ['LOCALAPPDATA']=tmp
 d=app.Document('work/test-template.psd','source.psd');app.DOC=d;client=app.app.test_client();h={'X-Moto-Token':app.TOKEN}
 d.assets['logo']={'name':'Team','image':Image.new('RGBA',(16,16),'red')}
 d.state['artworks']=[{'id':'a','asset':'logo','name':'Team','x':20,'y':40,'width':16,'height':12,'rotation':15,'opacity':.8,'visible':True,'color':'#ff0011'}]
 font=next(k for k in app.installed_fonts() if 'byd-name-font-stock' in k.lower())
 settings={'value':'TIPENE','font':font,'size':24,'fill':'#ffffff','gradient':{'start':'#ff0011','end':'#0055aa','angle':90}}
 text=client.post('/api/text',json=settings,headers=h).json
 d.state['artworks'].append({'id':'text','asset':text['id'],'name':'TIPENE','x':64,'y':64,'width':text['width'],'height':text['height'],'rotation':0,'opacity':1,'visible':True,'text':text['text']})
 d.state['palette']=['#FF0011','#0055AA']
 r=client.post('/api/layouts',json={'name':'Race kit','state':d.state},headers=h);assert r.status_code==200,r.json;key=r.json['id']
 p=PSDImage.new('RGB',(256,256));PixelLayer.frompil(Image.new('RGB',(256,256),'white'),p,'Base');p.save('work/v13-target.psd');target=app.Document('work/v13-target.psd','target.psd');app.DOC=target
 anchor=target.state['placement'];result=client.post('/api/layouts/'+key+'/add',json={},headers=h);assert result.status_code==200,result.json
 a=result.json['artworks'][0];assert (a['x'],a['y'],a['width'],a['height'])==(40,80,32,24);assert a['rotation']==15 and a['opacity']==.8 and a['color']=='#ff0011';assert a['id']!='a' and a['asset']!='logo';assert target.state['placement']==anchor;assert result.json['artworks'][1]['text']['gradient']==settings['gradient']
 target.update({'artworks':result.json['artworks']});target.composite_default();restored=app.load_project(io.BytesIO(app.project_bytes(target)));assert restored.state['artworks'][1]['text']['gradient']==settings['gradient']
 assert client.delete('/api/layouts/'+key,headers=h).status_code==200
 assert a['asset'] in target.assets and target.state['artworks']
 assert client.get('/api/layouts',headers=h).json==[]
 print('PASS persisted layout transfer, proportional scaling, colours/rotation/opacity, fresh IDs, target placement, independent deletion')

import json,urllib.request,io
from pathlib import Path
import sys,time
config=Path(sys.argv[1] if len(sys.argv)>1 else 'work/v13-packaged-session.json')
for attempt in range(50):
 if config.exists():break
 time.sleep(.1)
c=json.loads(config.read_text());base=c['url'].split('/?')[0];token=c['token']
def req(path,data=None,method=None,content_type='application/json'):
 body=json.dumps(data).encode() if data is not None and content_type=='application/json' else data
 r=urllib.request.Request(base+'/api/'+path,data=body,method=method,headers={'X-Moto-Token':token,'Content-Type':content_type})
 with urllib.request.urlopen(r,timeout=10) as response:return json.load(response)
boundary='MotoGearTestBoundary'
content=Path('work/test-template.psd').read_bytes()
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test.psd"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+content+f'\r\n--{boundary}--\r\n'.encode())
doc=req('open',body,content_type='multipart/form-data; boundary='+boundary)
fonts=req('fonts');font=next(f['id'] for f in fonts if 'byd-name-font-stock' in f['id'].lower())
t=req('text',{'value':'TEAM','font':font,'size':24,'gradient':{'start':'#ff0000','end':'#0000ff','angle':90}})
state=doc['state'];state['artworks']=[{'id':'test','asset':t['id'],'name':'TEAM','x':30,'y':40,'width':40,'height':20,'rotation':15,'opacity':1,'visible':True,'text':t['text']}]
saved=req('layouts',{'state':state,'name':'Packaged layout test'});result=req('layouts/'+saved['id']+'/add',{})
assert result['artworks'][0]['text']['gradient']['end']=='#0000ff';assert result['artworks'][0]['x']==30
assert len(req('layouts'))>=1
req('layouts/'+saved['id'],method='DELETE')
print('PASS packaged EXE startup, bundled fonts, gradient text and persistent layout API roundtrip')


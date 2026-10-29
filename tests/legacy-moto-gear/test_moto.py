import sys,io,hashlib,struct,json
from pathlib import Path
sys.path.insert(0,str(Path('outputs/Moto-Gear/source').resolve()))
from PIL import Image,ImageDraw
from packing import tga_bytes,pack_pnt,read_pnt
root=Path("N:/RIDER GEAR PSD's/Rider Gear/Stryder Gear/2019 Shift Black Label - Light")
existing=read_pnt((root/'!SHIFT STRIKE BLACK 76.pnt').read_bytes())
for stem,entry in existing.items():
 data=(root/'S STRIKE BLACK 76'/(stem+'.tga')).read_bytes()
 assert entry['md5']==hashlib.md5(data).digest()
 im=Image.open(io.BytesIO(data)).convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
 assert entry['rgba']==im.tobytes()
 print('Reference PNT matches source TGA:',stem)
image=Image.new('RGBA',(32,24),(180,20,50,173));image.putpixel((3,4),(12,34,56,240))
textures={stem:tga_bytes(image,stem!='rider') for stem in ['rider','rider_n','rider_r']}
packed=pack_pnt('Moto Gear test',textures);entries=read_pnt(packed)
for stem,data in textures.items():
 im=Image.open(io.BytesIO(data)); assert data[16]==(24 if stem=='rider' else 32)
 if stem!='rider':assert im.getchannel('A').getextrema()==(0,0)
 assert im.convert('RGB').getpixel((3,4))==(12,34,56)
 assert entries[stem]['rgba']==im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
 assert entries[stem]['md5']==hashlib.md5(data).digest()
print('TGA bit depths, black alpha, RGB preservation, orientation and PNT checksums: PASS')
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import BlendMode
p=PSDImage.new('RGB',(128,128),color=(255,255,255))
PixelLayer.frompil(Image.new('RGB',(128,128),'white'),p,'Base')
s=PixelLayer.frompil(Image.new('RGBA',(128,128),(128,128,128,255)),p,'Shading');s.blend_mode=BlendMode.MULTIPLY
n=PixelLayer.frompil(Image.new('RGB',(128,128),(128,128,255)),p,'Normal');n.visible=False
r=PixelLayer.frompil(Image.new('RGB',(128,128),(40,40,40)),p,'Spec');r.visible=False
p.save('work/test-template.psd')
import app
doc=app.Document('work/test-template.psd','Test gear.psd')
art=Image.new('RGBA',(32,32),(255,0,0,255));doc.assets['test']={'name':'Test logo','image':art}
doc.state['artworks']=[{'id':'test','asset':'test','name':'Test logo','x':64,'y':64,'width':32,'height':32,'rotation':0,'opacity':1,'visible':True}]
out=doc.composite_default();assert out.getpixel((64,64))==(128,0,0),out.getpixel((64,64))
assert len(doc.psd)==4
print('Artwork is shaded beneath selected layer and insertion is cleaned up: PASS')
doc.prepare_preview();assert set(doc.previews)=={'default'}
tex=doc.textures();assert Image.open(io.BytesIO(tex['rider_n'])).getchannel('A').getextrema()==(0,0)
app.DOC=doc
client=app.app.test_client();headers={'X-Moto-Token':app.TOKEN}
assert client.get('/api/document').status_code==403
assert client.post('/api/render',json=doc.state,headers={**headers,'Origin':'http://evil.example'}).status_code==403
saved=client.post('/api/project/save',json=doc.state,headers=headers);assert saved.status_code==200,saved.data[:100]
opened=client.post('/api/project/open',data={'file':(io.BytesIO(saved.data),'test.motogear')},headers=headers);assert opened.status_code==200,opened.data[:100]
assert app.DOC.state==doc.state
assert app.DOC.assets['test']['image'].tobytes()==art.tobytes()
print('Editable project save/reopen and local API access checks: PASS')
fonts=client.get('/api/fonts',headers=headers).get_json()
byd=next(f for f in fonts if f['id']=='BYD-Number-Font-Stock-1.otf')
text=client.post('/api/text',json={'value':'76','font':byd['id'],'size':240,'fill':'#ffffff','stroke':5,'outline':'#000000'},headers=headers)
assert text.status_code==200,text.data
created=text.get_json();assert created['width']>30 and created['height']>30
assert app.DOC.assets[created['id']]['image'].getchannel('A').getextrema()==(0,255)
assert created['text']['font']==byd['id']
print('Installed BYD Stock number rendering, outline and transparency: PASS')

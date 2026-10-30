import sys,numpy as np
from PIL import Image,ImageDraw,ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from psd_tools.constants import BlendMode
S=1024;rng=np.random.default_rng(7)
def art(n,col=None,alpha=255):
    im=Image.new('RGBA',(S,S),(0,0,0,0));d=ImageDraw.Draw(im)
    for k in range(n):
        x,y=rng.integers(0,S,2);r=int(rng.integers(30,300));c=col or tuple(int(v) for v in rng.integers(0,255,3))
        d.rectangle([x,y,x+r,y+r//2],fill=c+(alpha,))
    return im
psd=PSDImage.new('RGB',(S,S),color=(255,255,255))
# order bottom -> top like the user's panel (shown reversed in UI)
draft=Group.new(psd,'Draft')                       # colourways, pass-through
for name,col in [('Navy',(20,30,90)),('Honda',(200,20,30)),('White',(240,240,240))]:
    l=PixelLayer.frompil(art(30,col),draft,name)
    if name!='Honda': l.visible=False
sub=Group.new(draft,'Extra panels');sub.blend_mode=BlendMode.NORMAL;sub.visible=False   # hidden nested isolated group
PixelLayer.frompil(art(10),sub,'Panel A');inner=Group.new(sub,'Inner');inner.blend_mode=BlendMode.NORMAL
PixelLayer.frompil(art(6),inner,'Inner art')
nn=Group.new(psd,'Name Numbers')
PixelLayer.frompil(art(4,(0,0,0)),nn,'Old number')
sh=Group.new(psd,'Shading')
s=Image.fromarray(np.dstack([np.zeros((S,S,3),'uint8'),(rng.random((S,S))*120).astype('uint8')]),'RGBA').filter(ImageFilter.GaussianBlur(3))
l=PixelLayer.frompil(s,sh,'Shading');l.blend_mode=BlendMode.MULTIPLY
acc=Group.new(psd,'Acc');PixelLayer.frompil(art(3),acc,'Calque 95')
n=Group.new(psd,'Norm');PixelLayer.frompil(Image.new('RGBA',(S,S),(128,128,255,255)),n,'Forme 109');n.visible=False
r=Group.new(psd,'Reflect');PixelLayer.frompil(Image.new('RGB',(S,S),(20,20,20)),r,'Calque 123');r.visible=False
uv=PixelLayer.frompil(art(40,(0,255,0)),psd,'UV');uv.visible=False
x=PixelLayer.frompil(art(2,(255,0,0)),psd,'X');x.visible=False
psd.save(sys.argv[1]);print('ok')

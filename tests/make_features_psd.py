import sys,numpy as np
from PIL import Image,ImageDraw,ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from psd_tools.constants import BlendMode
S=2048;rng=np.random.default_rng(3)
psd=PSDImage.new('RGB',(S,S),color=(255,255,255))
def blobs(n,alpha=255,size=S,seed=0):
    im=Image.new('RGBA',(size,size),(0,0,0,0));d=ImageDraw.Draw(im)
    for k in range(n):
        x,y=rng.integers(0,size,2);r=int(rng.integers(30,size//3));d.ellipse([x,y,x+r,y+r],fill=tuple(int(v) for v in rng.integers(0,255,3))+(alpha,))
    return im
PixelLayer.frompil(Image.fromarray((rng.random((S,S,3))*255).astype('uint8')).filter(ImageFilter.GaussianBlur(20)),psd,'Base')
panels=Group.new(psd,'PANELS')  # pass-through
panel=Image.new('RGBA',(S,S),(0,0,0,0));ImageDraw.Draw(panel).polygon([(100,300),(1800,200),(1500,1700),(300,1900)],fill=(40,40,40,255))
PixelLayer.frompil(panel,panels,'Panel shape')
c1=PixelLayer.frompil(blobs(25),panels,'Clipped colour');c1.clipping=True
c2=PixelLayer.frompil(blobs(10,180),panels,'Clipped overlay');c2.clipping=True;c2.blend_mode=BlendMode.OVERLAY
m=PixelLayer.frompil(blobs(30),psd,'Masked art');mk=Image.new('L',(S,S),0);ImageDraw.Draw(mk).rectangle([200,200,1400,1200],fill=255);m.remove_mask() if m.has_mask() else None;m.create_mask(mk.filter(ImageFilter.GaussianBlur(30)))
o=PixelLayer.frompil(blobs(12),psd,'60% opacity');o.opacity=153
f=PixelLayer.frompil(blobs(12),psd,'50% fill');f.fill_opacity=128
iso=Group.new(psd,'ISOLATED');iso.blend_mode=BlendMode.NORMAL
PixelLayer.frompil(blobs(8),iso,'iso base');sc=PixelLayer.frompil(blobs(8),iso,'iso screen');sc.blend_mode=BlendMode.SCREEN
mg=Group.new(psd,'MULTIPLY GROUP');mg.blend_mode=BlendMode.MULTIPLY;mg.opacity=200
PixelLayer.frompil(blobs(6),mg,'in multiply group')
# small odd-offset layers
for i,(x,y) in enumerate([(13,7),(1001,999),(1777,333)]):
    im=Image.new('RGBA',(S,S),(0,0,0,0));ImageDraw.Draw(im).text((x,y),'DG 76 TEST',fill=(255,255,0,255),font_size=60);PixelLayer.frompil(im,psd,f'Small {i}')
sl=PixelLayer.frompil(blobs(20,200),psd,'Soft light');sl.blend_mode=BlendMode.SOFT_LIGHT
h=PixelLayer.frompil(blobs(20),psd,'Hidden');h.visible=False
sh=Image.fromarray(np.dstack([np.zeros((S,S,3),'uint8'),(rng.random((S,S))*140).astype('uint8')]),'RGBA').filter(ImageFilter.GaussianBlur(4))
l=PixelLayer.frompil(sh,psd,'SHADING');l.blend_mode=BlendMode.MULTIPLY
n=Group.new(psd,'NORM');PixelLayer.frompil(Image.new('RGBA',(S,S),(128,128,255,255)),n,'N');n.visible=False
psd.save(sys.argv[1]);print('saved')

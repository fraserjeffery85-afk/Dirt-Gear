import sys,numpy as np
from PIL import Image,ImageDraw,ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from psd_tools.constants import BlendMode
S=4096;rng=np.random.default_rng(1)
psd=PSDImage.new('RGB',(S,S),color=(30,30,30))
base=Image.fromarray((rng.random((S,S,3))*40+100).astype('uint8'));PixelLayer.frompil(base,psd,'Base')
for g in range(6):
    grp=Group.new(psd,f'COLOURWAY {g}')
    for i in range(8):
        im=Image.new('RGBA',(S,S),(0,0,0,0));d=ImageDraw.Draw(im)
        for k in range(40):
            x,y=rng.integers(0,S,2);r=int(rng.integers(50,400));d.ellipse([x,y,x+r,y+r],fill=tuple(int(v) for v in rng.integers(0,255,3))+(255,))
        PixelLayer.frompil(im,grp,f'Design {g}.{i}')
    if g>1: grp.visible=False
logos=Group.new(psd,'LOGOS')
for i in range(10):
    im=Image.new('RGBA',(S,S),(0,0,0,0));d=ImageDraw.Draw(im);x,y=rng.integers(0,S-600,2);d.rectangle([x,y,x+500,y+200],fill=(255,255,255,255));PixelLayer.frompil(im,logos,f'Logo {i}')
sh=Image.fromarray(np.dstack([np.zeros((S,S,3),'uint8'),(rng.random((S,S))*120).astype('uint8')]),'RGBA').filter(ImageFilter.GaussianBlur(3))
l=PixelLayer.frompil(sh,psd,'SHADING');l.blend_mode=BlendMode.MULTIPLY
n=Group.new(psd,'NORM');PixelLayer.frompil(Image.fromarray((rng.random((S,S,3))*255).astype('uint8')).convert('RGBA'),n,'N');n.visible=False
sp=Group.new(psd,'SPEC');PixelLayer.frompil(Image.new('RGB',(S,S),(40,40,40)),sp,'R');sp.visible=False
psd.save(sys.argv[1]);print('saved')

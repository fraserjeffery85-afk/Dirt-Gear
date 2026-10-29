import sys
from PIL import Image, ImageDraw, ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from psd_tools.constants import BlendMode
S=1024
out=sys.argv[1]
psd=PSDImage.new('RGB',(S,S),color=(30,30,30))
base=Image.new('RGB',(S,S),(24,26,30));d=ImageDraw.Draw(base)
d.rectangle([0,0,S//2,S//2],fill=(232,232,226)); d.rectangle([S//2,0,S,S//2],fill=(30,60,140))
d.rectangle([0,S//2,S,S],fill=(20,22,26))
PixelLayer.frompil(base,psd,'Base colour')
cw=Group.new(psd,'COLOURWAY')
a=Image.new('RGBA',(S,S),(0,0,0,0));da=ImageDraw.Draw(a)
for i in range(6): da.polygon([(i*170,S//2),(i*170+90,S//2),(i*170+40,S),(i*170-50,S)],fill=(235,90,20,255))
PixelLayer.frompil(a,cw,'Orange stripes')
b=Image.new('RGBA',(S,S),(0,0,0,0));db=ImageDraw.Draw(b)
for i in range(6): db.polygon([(i*170,S//2),(i*170+90,S//2),(i*170+40,S),(i*170-50,S)],fill=(40,200,120,255))
l=PixelLayer.frompil(b,cw,'Green stripes'); l.visible=False
logos=Group.new(psd,'OLD LOGOS')
c=Image.new('RGBA',(S,S),(0,0,0,0));dc=ImageDraw.Draw(c);dc.ellipse([120,120,380,380],outline=(200,30,30,255),width=24)
PixelLayer.frompil(c,logos,'Creator logo')
sh=Image.new('RGBA',(S,S),(0,0,0,0));ds=ImageDraw.Draw(sh)
for y in range(0,S,64): ds.line([(0,y),(S,y+40)],fill=(0,0,0,90),width=18)
sh=sh.filter(ImageFilter.GaussianBlur(10))
sl=PixelLayer.frompil(sh,psd,'SHADING'); sl.blend_mode=BlendMode.MULTIPLY
n=Group.new(psd,'NORM'); PixelLayer.frompil(Image.new('RGBA',(S,S),(128,128,255,255)),n,'Normal fabric'); n.visible=False
sp=Group.new(psd,'SPEC'); PixelLayer.frompil(Image.new('RGB',(S,S),(40,40,40)),sp,'Reflection'); sp.visible=False
psd.save(out); print('ok',out)

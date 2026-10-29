import sys,time,numpy as np
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[1]/'source'))
from PIL import Image
from psd_tools import PSDImage
import fastpreview as fp
path=sys.argv[1];scale=float(sys.argv[2]) if len(sys.argv)>2 else None
psd=PSDImage.open(path)
if scale is None: scale=min(1.0,1400/max(psd.size))
cache={}
def source(layer,kind):
    k=id(layer)
    if k not in cache: cache[k]=fp.layer_data(layer,scale)
    return fp.as_float(cache[k],kind)
t=time.time();fast=fp.composite(psd,scale,source);t1=time.time()-t
t=time.time();fast2=fp.composite(psd,scale,source);t2=time.time()-t
print(f'scale {scale:.3f} size {fast.size} fast cold {t1:.2f}s warm {t2:.2f}s')
if '--nofull' in sys.argv: sys.exit()
t=time.time();full=psd.composite(ignore_preview=True,apply_icc=False).convert('RGB');tf=time.time()-t
ref=full.resize(fast.size,Image.Resampling.BOX)
d=np.abs(np.asarray(ref,dtype=np.int16)-np.asarray(fast,dtype=np.int16))
print(f'full {tf:.2f}s  diff mean {d.mean():.3f} p99 {np.percentile(d,99):.1f} p99.9 {np.percentile(d,99.9):.1f} max {d.max()}')
fast.save(path+'.fast.png');ref.save(path+'.ref.png')

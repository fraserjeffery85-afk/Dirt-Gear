import json,math
from pathlib import Path
p=Path('outputs/Moto-Gear/source/static/rider.json');mesh=json.loads(p.read_text(encoding='utf-8'));v=mesh['vertices'];assert mesh.get('stride',8)==8
sub=lambda a,b:[x-y for x,y in zip(a,b)]
dot=lambda a,b:sum(x*y for x,y in zip(a,b))
cross=lambda a,b:[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def unit(a):
 length=math.sqrt(dot(a,a));return [x/max(length,1e-12) for x in a]
rows=[v[i:i+8] for i in range(0,len(v),8)];sums={}
for i in range(0,len(rows),3):
 a,b,c=rows[i:i+3];e1=sub(b[:3],a[:3]);e2=sub(c[:3],a[:3]);du1,dv1=sub(b[6:8],a[6:8]);du2,dv2=sub(c[6:8],a[6:8]);d=du1*dv2-du2*dv1
 if abs(d)<1e-12:continue
 t=[(x*dv2-y*dv1)/d for x,y in zip(e1,e2)];bit=[(y*du1-x*du2)/d for x,y in zip(e1,e2)]
 weight=math.sqrt(dot(cross(e1,e2),cross(e1,e2)))
 for r in (a,b,c):
  acc=sums.setdefault(tuple(r),[0.]*6)
  for j,x in enumerate(t+bit):acc[j]+=x*weight
out=[]
for r in rows:
 n=unit(r[3:6]);acc=sums.get(tuple(r),[0.]*6);t=sub(acc[:3],[x*dot(n,acc[:3]) for x in n])
 if dot(t,t)<1e-12:t=cross([0,1,0] if abs(n[1])<.9 else [1,0,0],n)
 t=unit(t);sign=-1 if dot(cross(n,t),acc[3:])<0 else 1
 out.extend(r+[round(x,6) for x in t]+[sign])
mesh.update(stride=12,vertices=out);p.write_text(json.dumps(mesh,separators=(',',':')),encoding='utf-8');print('Added UV tangent frames for',len(rows),'vertices')

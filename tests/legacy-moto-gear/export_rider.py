import bpy,json
from pathlib import Path
out=Path('outputs/Moto-Gear/source/static/rider.json')
items=[]
for o in bpy.data.objects:
 if o.type!='MESH' or o.hide_render:continue
 deps=bpy.context.evaluated_depsgraph_get();obj=o.evaluated_get(deps);mesh=obj.to_mesh();mesh.calc_loop_triangles();uv=mesh.uv_layers.active
 mesh.calc_tangents(uvmap=uv.name)
 data=[]
 for tri in mesh.loop_triangles:
  for li in tri.loops:
   loop=mesh.loops[li];p=obj.matrix_world@mesh.vertices[loop.vertex_index].co;n=obj.matrix_world.to_3x3()@mesh.corner_normals[li].vector;n.normalize();t=uv.data[li].uv;tangent=obj.matrix_world.to_3x3()@loop.tangent;tangent.normalize();sign=loop.bitangent_sign*(-1 if obj.matrix_world.to_3x3().determinant()<0 else 1)
   data.extend([round(v,6) for v in (p.x,p.z,-p.y,n.x,n.z,-n.y,t.x,t.y,tangent.x,tangent.z,-tangent.y,sign)])
 items.extend(data);obj.to_mesh_clear()
out.write_text(json.dumps({'name':'WBD Rider — original paint UV','stride':12,'vertices':items},separators=(',',':')))
print('Exported vertices',len(items)//12,'bytes',out.stat().st_size)

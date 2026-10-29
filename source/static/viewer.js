'use strict';
// Small offline WebGL viewer. Mesh coordinates and UVs come from the supplied Blender model.
window.DirtRider={async create(canvas){
 const gl=canvas.getContext('webgl',{antialias:true,alpha:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('3D needs graphics acceleration. The 2D editor is still available.');
 const mesh=await(await fetch('/static/rider.json')).json();
 const data=new Float32Array(mesh.vertices),count=data.length/12;
 const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
 for(let i=0;i<data.length;i+=12)for(let j=0;j<3;j++){lo[j]=Math.min(lo[j],data[i+j]);hi[j]=Math.max(hi[j],data[i+j])}
 const height=hi[1]-lo[1],centre=lo.map((x,i)=>(x+hi[i])/2);
 for(let i=0;i<data.length;i+=12)for(let j=0;j<3;j++)data[i+j]=(data[i+j]-centre[j])*2/height;
 const vert=`attribute vec3 position;attribute vec3 normal;attribute vec2 uv;attribute vec4 tangent;
 uniform float yaw;uniform float pitch;uniform float distance;uniform float aspect;uniform float panX;uniform float panY;
 varying vec2 tex;varying vec3 norm;varying vec4 tang;varying vec3 viewPos;
 void main(){float cy=cos(yaw),sy=sin(yaw),cx=cos(pitch),sx=sin(pitch);
 mat3 ry=mat3(cy,0.,-sy,0.,1.,0.,sy,0.,cy);mat3 rx=mat3(1.,0.,0.,0.,cx,sx,0.,-sx,cx);
 vec3 p=rx*ry*position;norm=rx*ry*normal;tang=vec4(rx*ry*tangent.xyz,tangent.w);tex=uv;p.xy+=vec2(panX,panY);p.z-=distance;viewPos=p;
 gl_Position=vec4(p.x*2.8/aspect,p.y*2.8,-1.004*p.z-.2004,-p.z);}`;
 const frag=`precision mediump float;
 uniform sampler2D paint;uniform sampler2D normalMap;uniform sampler2D reflectionMap;
 uniform float useNormals;uniform float useReflections;
 varying vec2 tex;varying vec3 norm;varying vec4 tang;varying vec3 viewPos;
 void main(){
  vec3 n=normalize(norm);vec3 t=normalize(tang.xyz-n*dot(n,tang.xyz));vec3 b=normalize(cross(n,t))*tang.w;
  vec3 detail=texture2D(normalMap,tex).rgb*2.-1.;detail.xy=mix(vec2(0.),detail.xy,useNormals);detail.z=mix(1.,max(.001,detail.z),useNormals);
  n=normalize(mat3(t,b,n)*normalize(detail));if(!gl_FrontFacing)n=-n;
  vec3 light=normalize(vec3(-.4,.7,1.)),eye=normalize(-viewPos);
  float key=max(0.,dot(n,light));float fill=max(0.,dot(n,normalize(vec3(.8,.2,.6))));
  vec3 colour=texture2D(paint,tex).rgb*(.55+.35*key+.10*fill);
  vec3 r=reflect(-eye,n);
  // Studio softboxes reflected in the surface; the backdrop itself stays black.
  float box1=pow(max(0.,dot(r,normalize(vec3(-.7,.8,1.)))),18.);
  float box2=pow(max(0.,dot(r,normalize(vec3(.8,.3,.8)))),30.);
  float highlight=pow(max(0.,dot(n,normalize(light+eye))),48.);
  vec3 mask=texture2D(reflectionMap,tex).rgb*useReflections;
  float fresnel=.22+.78*pow(1.-max(0.,dot(n,eye)),5.);
  vec3 environment=vec3(.85,.91,1.)*box1+vec3(1.,.91,.8)*box2;
  colour+=mask*(environment*(.30+.45*fresnel)+highlight*.4);
  gl_FragColor=vec4(clamp(colour,0.,1.),1.);
 }`;
 function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
 const vs=shader(gl.VERTEX_SHADER,vert),fs=shader(gl.FRAGMENT_SHADER,frag),program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.deleteShader(vs);gl.deleteShader(fs);gl.useProgram(program);
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
 for(const [name,size,offset] of [['position',3,0],['normal',3,12],['uv',2,24],['tangent',4,32]]){const loc=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,48,offset)}
 const uniforms=Object.fromEntries(['yaw','pitch','distance','aspect','panX','panY','useNormals','useReflections'].map(k=>[k,gl.getUniformLocation(program,k)]));
 const textures=[];
 const ext=gl.getExtension('EXT_texture_filter_anisotropic');
 for(const [i,name,pixel] of [[0,'paint',[190,190,180,255]],[1,'normalMap',[128,128,255,255]],[2,'reflectionMap',[0,0,0,255]]]){
  const texture=gl.createTexture();textures.push(texture);gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,texture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(pixel));gl.uniform1i(gl.getUniformLocation(program,name),i);
 }
 function upload(i,image){
  gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,textures[i]);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
  let source=image,w=image.naturalWidth||image.width,h=image.naturalHeight||image.height;const limit=gl.getParameter(gl.MAX_TEXTURE_SIZE);
  if(w>limit||h>limit){source=document.createElement('canvas');const ratio=limit/Math.max(w,h);source.width=w=Math.max(1,Math.floor(w*ratio));source.height=h=Math.max(1,Math.floor(h*ratio));source.getContext('2d').drawImage(image,0,0,w,h)}
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);
  if((w&(w-1))===0&&(h&(h-1))===0){gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR)}else gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
  if(ext)gl.texParameterf(gl.TEXTURE_2D,ext.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(8,gl.getParameter(ext.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
 }
 gl.enable(gl.DEPTH_TEST);gl.clearColor(0,0,0,1);let normals=true,reflections=true;
 let yaw=0,pitch=0,distance=3.8,panX=0,panY=0,panMode=false,drag=null,frame=0;
 function render(){frame=0;gl.viewport(0,0,canvas.width,canvas.height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniform1f(uniforms.useNormals,normals?1:0);gl.uniform1f(uniforms.useReflections,reflections?1:0);gl.uniform1f(uniforms.panX,panX);gl.uniform1f(uniforms.panY,panY);gl.uniform1f(uniforms.yaw,yaw);gl.uniform1f(uniforms.pitch,pitch);gl.uniform1f(uniforms.distance,distance);gl.uniform1f(uniforms.aspect,canvas.width/canvas.height);gl.drawArrays(gl.TRIANGLES,0,count)}
 function draw(){if(!frame)frame=requestAnimationFrame(render)}
 function resize(){const r=canvas.getBoundingClientRect(),dpr=Math.min(2,devicePixelRatio||1);canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));draw()}
 canvas.addEventListener('contextmenu',e=>e.preventDefault());
 canvas.addEventListener('pointerdown',e=>{e.preventDefault();drag={x:e.clientX,y:e.clientY,yaw,pitch,panX,panY,pan:panMode||e.shiftKey||e.button===1||e.button===2};canvas.setPointerCapture(e.pointerId)});
 canvas.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
 if(drag.pan){const units=2*distance/(2.8*Math.max(1,canvas.clientHeight));panX=drag.panX+dx*units;panY=drag.panY-dy*units}
 else{yaw=drag.yaw+dx*.008;pitch=Math.max(-1.3,Math.min(1.3,drag.pitch+dy*.008))}draw()});
 for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,()=>drag=null);
 canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(1.4,Math.min(8,distance*Math.exp(e.deltaY*.001)));draw()},{passive:false});
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();document.getElementById('viewerStatus').textContent='Graphics connection lost. Reopen Dirt Gear to restore 3D.'});
 resize();return {resize,setPanMode(enabled){panMode=enabled;canvas.style.cursor=enabled?'move':'grab'},pan(dx,dy){panX+=dx;panY+=dy;draw()},setTextures(paint,normal,reflection){upload(0,paint);upload(1,normal);upload(2,reflection);draw()},setMaps(n,r){normals=n;reflections=r;draw()},setView(angle){yaw=angle;pitch=0;draw()},reset(){yaw=0;pitch=0;distance=3.8;panX=panY=0;draw()}};
}};

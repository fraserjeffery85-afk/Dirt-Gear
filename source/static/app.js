'use strict';
const $=id=>document.getElementById(id);
const token=new URLSearchParams(location.search).get('token')||'';
let doc=null,state=null,selected=null,view='default',images={},assetImages={},scale=1,zoom=1,pan={x:0,y:0},drag=null,ready=false,dirty=false,undo=[],redo=[],toastTimer,fonts=[],editingText=null,desktop=false,expandedGroups=new Set(),tintCache=new Map(),proofKey='',proofWanted='',proofTimer=null,proofBusy=false,artDragId=null,groupDrag=false,lastFieldSelection=null,previewEpoch=0,docStamp=0,visTimer=null,visBusy=false,visAgain=false,fullProofKey='',fullPreviewLoading=new Set();
const canvas=$('canvas'),ctx=canvas.getContext('2d');
const url=path=>`/api/${path}${path.includes('?')?'&':'?'}token=${encodeURIComponent(token)}`;
function notify(message,error=false){$('toast').textContent=message;$('toast').className=error?'error':'';$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,error?12000:4500)}
async function api(path,body,method='POST'){
 const opts={method,headers:{'X-Dirt-Token':token}};if(desktop)opts.headers['X-Dirt-Desktop']='1';
 if(body instanceof FormData)opts.body=body;else if(body!==undefined){opts.body=JSON.stringify(body);opts.headers['Content-Type']='application/json'}
 const r=await fetch('/api/'+path,opts);if(!r.ok){let e;try{e=await r.json()}catch{e={error:`Request failed (${r.status})`}}throw Error(e.error)}return r;
}
async function busy(title,fn,detail='Large PSDs can take a moment. Keep this window open.'){
 $('busyTitle').textContent=title;$('busyDetail').textContent=detail;$('busyDialog').showModal();
 try{return await fn()}catch(e){notify(e.message,true);console.error(e)}finally{$('busyDialog').close()}
}
function snapshot(){if(!state)return;undo.push(JSON.stringify(state.artworks));if(undo.length>40)undo.shift();redo=[];dirty=true}
function undoAction(back=false){const from=back?redo:undo,to=back?undo:redo;if(!from.length)return;to.push(JSON.stringify(state.artworks));state.artworks=JSON.parse(from.pop());if(!state.artworks.some(x=>x.id===selected))selected=null;lastFieldSelection=null;dirty=true;renderArtList();draw();}
function imageLoad(src){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Could not load image'));im.src=src})}
function current(){return state?.artworks.find(x=>x.id===selected)}
let lastRev=0;
function getState(){state.name=$('gearName').value.trim()||'Dirt Gear';lastRev=Math.max(Date.now(),lastRev+1);state.rev=lastRev;return state}
function readStoredPalette(){try{return JSON.parse(localStorage.getItem('dirtGearPalette')||localStorage.getItem('motoGearPalette')||'[]')}catch{return[]}}
function storePalette(){try{localStorage.setItem('dirtGearPalette',JSON.stringify(state.palette))}catch{}}
function canonicalColor(value){return /^#[0-9a-f]{6}$/i.test(value||'')?value.toUpperCase():null}
function rememberColor(value){const color=canonicalColor(value);if(!color||!state)return;state.palette=[color,...(state.palette||[]).filter(c=>c!==color)].slice(0,32);storePalette();dirty=true;renderSwatches()}
function renderSwatches(){renderGradientSwatches();if(typeof renderOverlaySwatches==='function')renderOverlaySwatches();for(const[id,inText]of[['swatches',false],['textSwatches',true]]){const box=$(id);box.replaceChildren();const colors=state?.palette||[];if(!colors.length&&!inText){const p=document.createElement('span');p.className='hint';p.textContent='Saved colours appear here.';box.append(p)}for(const color of colors){const button=document.createElement('button');button.type='button';button.className='swatch';button.style.background=color;button.title=color;button.setAttribute('aria-label','Use colour '+color);button.onclick=()=>{if(inText){$('textFill').value=color.toLowerCase();queueFontPreview()}else{setColorInputs(color);const art=current();if(art&&!art.text){snapshot();setOverlay(art,{mode:'solid',color,strength:currentOverlay(art)?.strength??1})}}};box.append(button)}}}
function setColorInputs(color){const exact=canonicalColor(color);if(!exact)return;$('artColorPicker').value=exact.toLowerCase();$('artColorHex').value=exact}
async function acceptDoc(data){docStamp=Date.now();previewEpoch++;proofFailedKey='';clearTimeout(proofTimer);proofTimer=null;doc=data;state=data.state;images={};assetImages={};selected=null;ready=false;dirty=false;undo=[];redo=[];expandedGroups=new Set(data.layers.filter(l=>l.group).map(l=>l.id));
 try{const saved=readStoredPalette();state.palette=[...new Set([...(state.palette||[]),...saved].map(c=>canonicalColor(c)).filter(Boolean))].slice(0,32)}catch{state.palette=state.palette||[]}
 $('fileName').textContent=data.filename;$('fileMeta').textContent=`${data.width} × ${data.height} · ${data.layers.length} layers`;$('gearName').value=state.name;
 $('saveProject').disabled=false;$('saveForLater').disabled=false;
 for(const asset of data.assets)assetImages[asset.id]=await imageLoad(url('artwork/'+asset.id));
 renderLayers();renderArtList();renderSwatches();await prepare();
 if(!state.shading){notify('No shading layer found by name. Drag “Your added layers” onto your shading layer so logos and text sit underneath it.',true);document.querySelector('.added-group')?.classList.add('attention')}
}
async function prepare(){
 const setupWork=async()=>{
  const data=await(await api('setup',getState())).json();doc=data;state=data.state;
  await loadPreviews();ready=true;dirty=true;$('empty').hidden=true;canvas.hidden=false;document.body.classList.add('has-doc');
  for(const id of ['addArtwork','pasteArtwork','addName','addNumber','exportPnt','exportTga','proofBtn','open3d','openLogoLibrary','openLayouts'])$(id).disabled=false;$('installPnt').disabled=!$('gameModel').value;
  $('canvasStatus').textContent='Layout preview · drag artwork to position';renderLayers();setTimeout(loadThumbs,50);renderArtList();resize();
 };if($('busyDialog').open)await setupWork();else await busy('Preparing your template',setupWork);
}
async function loadPreviews(){const stamp=Date.now();previewEpoch++;proofFailedKey='';images={};proofKey='';proofWanted='';fullProofKey='';fullPreviewLoading.clear();clearTimeout(proofTimer);proofTimer=null;images.default=await imageLoad(url(`preview/default?v=${stamp}`))}
function renderLayers(){const list=$('layers'),artList=$('artworkList');artList.remove();list.replaceChildren();if(!doc)return;
 const normals=new Set(state.normal_layers||[state.normal]);
 const toggleVisibility=(layer,checked,row)=>{state.visibility[layer.id]=checked;dirty=true;row?.classList.toggle('off',!checked);queueVisibilityUpdate()};
 const visible=doc.layers.filter(layer=>{const parents=layer.id.split('.').slice(0,-1);let ancestor='';return !parents.some(part=>{ancestor=ancestor?ancestor+'.'+part:part;return !expandedGroups.has(ancestor)})});
 let anchor=state.placement||'';while(anchor&&!visible.some(layer=>layer.id===anchor))anchor=anchor.includes('.')?anchor.slice(0,anchor.lastIndexOf('.')):'';
 const addArtworkGroup=depth=>{const row=document.createElement('div');row.className='added-group';row.draggable=true;row.style.paddingLeft=(13+depth*10)+'px';row.title='Drag this section onto a PSD layer to place all artwork below it';row.innerHTML='<span class="drag-handle">⠿</span><span>YOUR ADDED LAYERS</span><span class="role">DRAG TO PLACE</span>';
  row.ondragstart=e=>{groupDrag=true;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('application/x-dirt-layer-group','1')};row.ondragend=()=>{groupDrag=false;document.querySelectorAll('.layer.drop-target').forEach(x=>x.classList.remove('drop-target'))};
  list.append(row);artList.hidden=false;list.append(artList)};
 if(!anchor)addArtworkGroup(0);
 for(let i=0;i<visible.length;i++){const layer=visible[i];
 const row=document.createElement('div');row.className='layer'+(layer.group?' group':'')+(!state.visibility[layer.id]?' off':'');row.style.paddingLeft=(13+layer.depth*10)+'px';
 const input=document.createElement('input');input.type='checkbox';input.checked=state.visibility[layer.id];input.id='layer-'+layer.id;input.setAttribute('aria-label','Show '+layer.name);
 const isMap=normals.has(layer.id)||layer.id===state.spec;input.disabled=isMap;input.title=isMap?'Used automatically for export':`Show ${layer.name}`;
 input.onchange=()=>toggleVisibility(layer,input.checked,row);
 const thumb=document.createElement('img');thumb.className='layer-thumb';thumb.alt='';thumb.decoding='async';thumb.dataset.src=url('layer/thumbnail/'+layer.id+'?d='+docStamp);
 const label=document.createElement(layer.group?'button':'label');if(layer.group){label.type='button';label.className='layer-expand';label.onclick=()=>{expandedGroups.has(layer.id)?expandedGroups.delete(layer.id):expandedGroups.add(layer.id);renderLayers()}}else label.htmlFor=input.id;label.textContent=(layer.group?(expandedGroups.has(layer.id)?'▾ ':'▸ '):'')+layer.name;label.title=layer.name;
 const role=document.createElement('span');role.className='role';role.textContent=layer.id===state.shading?'SHADE':normals.has(layer.id)?'NORM':layer.id===state.spec?'SPEC':layer.kind==='smartobject'?'ART':'';
 row.append(input,thumb,label,role);
 if(!isMap){row.ondragover=e=>{if(groupDrag){e.preventDefault();e.dataTransfer.dropEffect='move';row.classList.add('drop-target')}};row.ondragleave=()=>row.classList.remove('drop-target');row.ondrop=e=>{if(!groupDrag)return;e.preventDefault();groupDrag=false;state.placement=layer.id;dirty=true;renderLayers();draw();document.querySelector('.added-group')?.classList.remove('attention');notify('Added layers are now below '+layer.name)}}
 list.append(row);
 if(anchor===layer.id&&(!visible[i+1]||!visible[i+1].id.startsWith(anchor+'.')))addArtworkGroup(layer.depth);
 if(anchor&&layer.id.startsWith(anchor+'.')&&(!visible[i+1]||!visible[i+1].id.startsWith(anchor+'.')))addArtworkGroup(doc.layers.find(x=>x.id===anchor)?.depth||0);
 }
 if(!list.contains(artList))addArtworkGroup(0);
 loadThumbs();
}
function queueVisibilityUpdate(){
 document.body.classList.add('pending');$('canvasStatus').textContent='Updating preview…';
 clearTimeout(visTimer);visTimer=setTimeout(runVisibilityUpdate,350);
}
async function runVisibilityUpdate(){
 visTimer=null;if(visBusy){visAgain=true;return}
 visBusy=true;const epoch=previewEpoch;
 try{
  await api('setup',getState());if(epoch!==previewEpoch)return;
  const stamp=Date.now(),image=await imageLoad(url(`preview/default?v=${stamp}`));if(epoch!==previewEpoch)return;
  images.default=image;images.defaultFull=null;images.proof=null;images.proofFull=null;proofKey='';fullProofKey='';proofFailedKey='';delete images.normal;delete images.spec;
  draw();
 }catch(e){notify('Could not update the preview: '+e.message,true)}
 finally{visBusy=false;if(visAgain){visAgain=false;runVisibilityUpdate()}else if(!proofBusy)draw()}
}
// Thumbnails load after the preview, two at a time, so they never queue
// ahead of preview images in the browser's connection limit.
let thumbsActive=0;
function loadThumbs(){
 if(!ready)return;
 const pending=[...document.querySelectorAll('.layer-thumb[data-src]:not([src])')];
 while(thumbsActive<2&&pending.length){
  const img=pending.shift();thumbsActive++;
  const done=()=>{thumbsActive--;loadThumbs()};
  img.onload=done;img.onerror=done;img.src=img.dataset.src;
 }
}
function moveArtwork(id,delta){const i=state.artworks.findIndex(a=>a.id===id),j=i+delta;if(i<0||j<0||j>=state.artworks.length)return;snapshot();[state.artworks[i],state.artworks[j]]=[state.artworks[j],state.artworks[i]];renderArtList();draw()}
function renderArtList(){const list=$('artworkList');list.replaceChildren();if(!state?.artworks.length){const p=document.createElement('p');p.className='muted empty-note';p.textContent='Your logos, names and numbers will stack here.';list.append(p)}
 for(const art of [...(state?.artworks||[])].reverse()){
  const row=document.createElement('div');row.className='art-item'+(selected===art.id?' selected':'');row.draggable=true;row.title='Drag to change layer order';
  const choose=document.createElement('button');choose.type='button';choose.className='art-select';const im=document.createElement('img');im.src=assetImages[art.asset]?.src||url('artwork/'+art.asset);im.alt='';const span=document.createElement('span');span.textContent=art.name;choose.append(im,span);choose.onclick=()=>{selected=art.id;view='default';updateTabs();renderArtList();draw()};row.append(choose);
  for(const [symbol,delta,title]of [['↑',1,'Move layer up'],['↓',-1,'Move layer down']]){const button=document.createElement('button');button.type='button';button.className='order-button';button.textContent=symbol;button.title=title;button.setAttribute('aria-label',`${title}: ${art.name}`);button.disabled=delta===1?state.artworks.at(-1)===art:state.artworks[0]===art;button.onclick=()=>moveArtwork(art.id,delta);row.append(button)}
  row.ondragstart=e=>{artDragId=art.id;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',art.id);row.classList.add('dragging')};row.ondragend=()=>{artDragId=null;row.classList.remove('dragging')};row.ondragover=e=>{if(artDragId){e.preventDefault();e.dataTransfer.dropEffect='move';row.classList.add('drag-over')}};row.ondragleave=()=>row.classList.remove('drag-over');row.ondrop=e=>{e.preventDefault();row.classList.remove('drag-over');if(!artDragId||artDragId===art.id)return;const displayed=[...state.artworks].reverse(),from=displayed.findIndex(a=>a.id===artDragId);if(from<0)return;const [item]=displayed.splice(from,1);let to=displayed.findIndex(a=>a.id===art.id);if(e.clientY>row.getBoundingClientRect().top+row.offsetHeight/2)to++;displayed.splice(to,0,item);snapshot();state.artworks=displayed.reverse();artDragId=null;renderArtList();draw()};list.append(row)
 }updateFields();
}
function updateFields(){const art=current();$('transform').hidden=!art;$('artActions').hidden=!art;if(!art)return;
 if(lastFieldSelection!==art.id){$('lockRatio').checked=true;lastFieldSelection=art.id}
 $('editText').hidden=!art.text;$('textStretch').hidden=!art.text;
 if(art.text){const width=art.text.base_width||assetImages[art.asset]?.naturalWidth||art.width,height=art.text.base_height||assetImages[art.asset]?.naturalHeight||art.height;const percent=Math.round(100*art.width/(art.height*width/height));$('textWidth').value=Math.max(20,Math.min(500,percent));$('textWidthValue').textContent=percent+'%'}
 updateOverlayUI(art);
 for(const[id,key]of[['posX','x'],['posY','y'],['artWidth','width'],['artHeight','height']])if(document.activeElement!==$(id))$(id).value=Math.round(art[key]);
 $('rotation').value=art.rotation;$('rotationValue').textContent=Math.round(art.rotation)+'°';$('opacity').value=art.opacity*100;$('opacityValue').textContent=Math.round(art.opacity*100)+'%';
}
async function addAsset(item){assetImages[item.id]=await imageLoad(url('artwork/'+item.id));snapshot();const w=Math.min(doc.width*.24,item.width);const art={id:crypto.randomUUID(),asset:item.id,name:item.name,x:doc.width/2,y:doc.height/2,width:w,height:w*item.height/item.width,rotation:0,opacity:1,visible:true};state.artworks.push(art);selected=art.id;view='default';updateTabs();renderArtList();draw()}
async function rasterSvg(file){const text=await file.text();if(/<(script|foreignObject)\b|(?:href|src)\s*=\s*["']\s*(?:https?:|file:|\/\/)/i.test(text))throw Error('Use an SVG with embedded artwork and no external images or scripts.');
 const blob=new Blob([text],{type:'image/svg+xml'}),src=URL.createObjectURL(blob);try{const im=await imageLoad(src);const c=document.createElement('canvas');const width=im.naturalWidth||1,height=im.naturalHeight||1,target=Math.min(8192,Math.max(doc.width,doc.height));const ratio=Math.min(target/Math.max(width,height),(32*1024*1024/(width*height))**.5);c.width=Math.max(1,Math.round(width*ratio));c.height=Math.max(1,Math.round(height*ratio));c.getContext('2d').drawImage(im,0,0,c.width,c.height);const png=await new Promise(r=>c.toBlob(r,'image/png'));return new File([png],file.name.replace(/\.svg$/i,'')+'.png',{type:'image/png'})}finally{URL.revokeObjectURL(src)}}
async function addFiles(files){if(!ready){notify('Open a PSD and prepare its layers first.',true);return}await busy('Adding artwork',async()=>{for(let file of files){if(file.type==='image/svg+xml'||/\.svg$/i.test(file.name))file=await rasterSvg(file);const form=new FormData();form.append('file',file);await addAsset(await(await api('artwork',form)).json())}},'Your artwork stays on this computer.')}
async function nativePaste(){if(!ready)return;await busy('Reading clipboard',async()=>{const item=await(await api('clipboard',{})).json();if(item.svg){const file=await rasterSvg(new File([item.svg],'Illustrator artwork.svg',{type:'image/svg+xml'}));const form=new FormData();form.append('file',file);await addAsset(await(await api('artwork',form)).json())}else await addAsset(item)},'Looking for an image or SVG copied from your design app.')}
function resize(){const r=$('stage').getBoundingClientRect();const dpr=window.devicePixelRatio||1;canvas.width=Math.round(r.width*dpr);canvas.height=Math.round(r.height*dpr);draw()}
function metrics(){const r=$('stage').getBoundingClientRect();const fit=Math.min((r.width-65)/doc.width,(r.height-65)/doc.height);scale=fit*zoom;return {r,x:(r.width-doc.width*scale)/2+pan.x,y:(r.height-doc.height*scale)/2+pan.y}}
function artworkImage(a){const base=assetImages[a.asset];const ov=currentOverlay(a);if(!base||!ov)return base;const key=a.asset+'|'+JSON.stringify(ov);if(tintCache.has(key))return tintCache.get(key);
 const w=base.naturalWidth,h=base.naturalHeight,c=document.createElement('canvas');c.width=w;c.height=h;const g=c.getContext('2d');g.drawImage(base,0,0);
 const o=document.createElement('canvas');o.width=w;o.height=h;const og=o.getContext('2d');
 if(ov.mode==='solid')og.fillStyle=ov.color;else{const r=(ov.angle??90)*Math.PI/180,dx=Math.cos(r),dy=Math.sin(r),e=Math.max(1,Math.abs(dx)*(w-1)+Math.abs(dy)*(h-1)),cx=(w-1)/2,cy=(h-1)/2,gr=og.createLinearGradient(cx-dx*e/2,cy-dy*e/2,cx+dx*e/2,cy+dy*e/2);gr.addColorStop(0,ov.start);gr.addColorStop(1,ov.end);og.fillStyle=gr}
 og.fillRect(0,0,w,h);og.globalCompositeOperation='destination-in';og.drawImage(base,0,0);
 g.globalAlpha=ov.strength??1;g.drawImage(o,0,0);if(tintCache.size>40)tintCache.clear();tintCache.set(key,c);return c}
function snapAngle(degrees,free=false){return $('snapRotation').checked&&!free?Math.round(degrees/15)*15:degrees}
function previewKey(){return JSON.stringify([state.visibility,state.placement,state.normal_layers,state.spec,state.artworks])}
let proofFailedKey='';
function scheduleAccuratePreview(key){
 if(proofBusy){proofWanted=key;return}
 if(proofFailedKey===key||proofTimer&&proofWanted===key)return;
 clearTimeout(proofTimer);proofWanted=key;
 proofTimer=setTimeout(async()=>{
  proofTimer=null;if(!ready||!state)return;
  proofBusy=true;const requested=previewKey(),epoch=previewEpoch,payload=JSON.parse(JSON.stringify(getState()));
  let source;
  try{
   const response=await api('render/live',payload);source=URL.createObjectURL(await response.blob());
   const rendered=await imageLoad(source);
   if(epoch===previewEpoch&&previewKey()===requested){images.proof=rendered;images.proofFull=null;fullProofKey='';proofKey=requested;proofFailedKey='';if($('toast').textContent.startsWith('Your artwork is visible in editing view.'))$('toast').hidden=true}
  }catch(e){if(epoch===previewEpoch){proofFailedKey=requested;notify('Your artwork is visible in editing view. Shading could not refresh. Click Retry shading.',true)}}
  finally{
   if(source)URL.revokeObjectURL(source);proofBusy=false;
   if(ready&&state){draw();const latest=previewKey();if(state.artworks.some(a=>a.visible)&&latest!==proofKey&&latest!==proofFailedKey&&(!drag||drag.mode==='pan'))scheduleAccuratePreview(latest)}
  }
 },350);
}
function requestFullPreview(kind,key=''){const epoch=previewEpoch,tag=`${kind}|${key}|${epoch}`;if(fullPreviewLoading.has(tag))return;fullPreviewLoading.add(tag);imageLoad(url(`preview/${kind}?full=1&v=${Date.now()}`)).then(image=>{if(epoch!==previewEpoch||kind==='proof'&&key!==proofKey)return;images[kind+'Full']=image;if(kind==='proof')fullProofKey=key;draw()}).catch(e=>notify('Could not load the full-resolution preview: '+e.message,true)).finally(()=>fullPreviewLoading.delete(tag))}
let drawFrame=0;
function draw(){if(!drawFrame)drawFrame=requestAnimationFrame(()=>{drawFrame=0;paintCanvas()})}
function paintCanvas(){if(!doc||!ready)return;const {r,x,y}=metrics(),dpr=window.devicePixelRatio||1;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,r.width,r.height);ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);ctx.fillStyle='#939393';ctx.fillRect(0,0,doc.width,doc.height);ctx.beginPath();ctx.rect(0,0,doc.width,doc.height);ctx.clip();
 const hasArtwork=view==='default'&&state.artworks.some(a=>a.visible),key=hasArtwork?previewKey():'';
 const accurate=hasArtwork&&proofKey===key&&images.proof,needFull=view==='default'&&scale>1400/doc.width;
 if(needFull&&!drag){if(accurate&&(!images.proofFull||fullProofKey!==key))requestFullPreview('proof',key);else if(!hasArtwork&&!images.defaultFull)requestFullPreview('default')}
 const base=accurate?(needFull&&fullProofKey===key&&images.proofFull||images.proof):(needFull&&images.defaultFull||images[view]);if(base)ctx.drawImage(base,0,0,doc.width,doc.height);
 if(hasArtwork&&!accurate){
  for(const a of state.artworks){const im=artworkImage(a);if(!a.visible||!im)continue;ctx.save();ctx.translate(a.x,a.y);ctx.rotate(a.rotation*Math.PI/180);ctx.globalAlpha=a.opacity;ctx.drawImage(im,-a.width/2,-a.height/2,a.width,a.height);ctx.restore()}
  if(!drag||drag.mode==='pan')scheduleAccuratePreview(key)
 }
 ctx.restore();
 $('retryShading').hidden=!(hasArtwork&&!accurate&&proofFailedKey===key);
 const visPending=visBusy||!!visTimer;document.body.classList.toggle('pending',visPending||hasArtwork&&!accurate&&proofFailedKey!==key);$('canvasStatus').textContent=visPending?'Updating preview…':hasArtwork?(accurate?'Shaded preview · ready':proofFailedKey===key?'Editing preview · shading needs a retry':drag?'Editing preview · release to update shading':'Editing preview · updating shading…'):'Ready to add artwork';
 const a=current();if(a&&view==='default'){ctx.save();ctx.translate(x+a.x*scale,y+a.y*scale);ctx.rotate(a.rotation*Math.PI/180);ctx.strokeStyle='#D7FF3C';ctx.lineWidth=1.5;ctx.strokeRect(-a.width*scale/2,-a.height*scale/2,a.width*scale,a.height*scale);ctx.fillStyle='#D7FF3C';for(const [hx,hy] of [[a.width*scale/2,a.height*scale/2],[a.width*scale/2,0],[0,a.height*scale/2]])ctx.fillRect(hx-5,hy-5,10,10);ctx.beginPath();ctx.moveTo(0,-a.height*scale/2);ctx.lineTo(0,-a.height*scale/2-22);ctx.stroke();ctx.beginPath();ctx.arc(0,-a.height*scale/2-22,5,0,Math.PI*2);ctx.fill();ctx.restore()}
 $('zoomLabel').textContent=Math.round(scale*100)+'%';
}
function point(e){const b=canvas.getBoundingClientRect(),m=metrics();return{x:(e.clientX-b.left-m.x)/scale,y:(e.clientY-b.top-m.y)/scale}}
function localPoint(p,a){const rad=-a.rotation*Math.PI/180,dx=p.x-a.x,dy=p.y-a.y;return{x:dx*Math.cos(rad)-dy*Math.sin(rad),y:dx*Math.sin(rad)+dy*Math.cos(rad)}}
canvas.addEventListener('pointerdown',e=>{if(!ready)return;const p=point(e);if(e.button===1||e.altKey){drag={mode:'pan',sx:e.clientX,sy:e.clientY,px:pan.x,py:pan.y};canvas.setPointerCapture(e.pointerId);return}if(view!=='default')return;let a=current();let mode='move';if(a){const q=localPoint(p,a);if(Math.hypot(q.x-a.width/2,q.y-a.height/2)<14/scale)mode='resize';else if(Math.hypot(q.x-a.width/2,q.y)<14/scale)mode='resize-x';else if(Math.hypot(q.x,q.y-a.height/2)<14/scale)mode='resize-y';else if(Math.hypot(q.x,q.y+a.height/2+22/scale)<14/scale)mode='rotate';else a=null}
 if(!a)a=[...state.artworks].reverse().find(a=>{const q=localPoint(p,a);return a.visible&&Math.abs(q.x)<=a.width/2&&Math.abs(q.y)<=a.height/2});selected=a?.id||null;if(a){snapshot();drag={mode,start:p,original:{...a}};canvas.setPointerCapture(e.pointerId)}renderArtList();draw()});
canvas.addEventListener('pointermove',e=>{if(!ready)return;const p=point(e);$('coordinate').textContent=`${Math.round(p.x)}, ${Math.round(p.y)}`;if(!drag)return;if(drag.mode==='pan'){pan.x=drag.px+e.clientX-drag.sx;pan.y=drag.py+e.clientY-drag.sy;draw();return}const a=current();if(!a)return;const o=drag.original;if(drag.mode==='move'){a.x=o.x+p.x-drag.start.x;a.y=o.y+p.y-drag.start.y}else if(drag.mode==='rotate'){a.rotation=snapAngle(Math.atan2(p.y-a.y,p.x-a.x)*180/Math.PI+90,e.shiftKey);if(a.rotation>180)a.rotation-=360}else{const q=localPoint(p,a),width=Math.max(1,Math.min(16384,q.x*2)),height=Math.max(1,Math.min(16384,q.y*2)),keepRatio=$('lockRatio').checked&&!e.shiftKey;if(drag.mode==='resize'){if(keepRatio){const sx=width/o.width,sy=height/o.height,ratio=Math.abs(sx-1)>=Math.abs(sy-1)?sx:sy;a.width=Math.max(1,Math.min(16384,o.width*ratio));a.height=Math.max(1,Math.min(16384,o.height*ratio))}else{a.width=width;a.height=height}}else if(drag.mode==='resize-x'){a.width=width;if(keepRatio)a.height=Math.max(1,Math.min(16384,o.height*a.width/o.width))}else if(drag.mode==='resize-y'){a.height=height;if(keepRatio)a.width=Math.max(1,Math.min(16384,o.width*a.height/o.height))}}updateFields();draw()});
canvas.addEventListener('pointerup',()=>{drag=null;draw()});canvas.addEventListener('pointercancel',()=>{drag=null;draw()});
canvas.addEventListener('wheel',e=>{if(!ready)return;e.preventDefault();zoom=Math.min(8,Math.max(.2,zoom*(e.deltaY<0?1.12:1/1.12)));draw()},{passive:false});
for(const[id,key]of[['posX','x'],['posY','y'],['artWidth','width'],['artHeight','height']]){$(id).onfocus=()=>snapshot();$(id).oninput=()=>{const a=current();if(!a||$(id).value==='')return;let n=Number($(id).value);if(!Number.isFinite(n))return;if(key==='width'||key==='height')n=Math.max(1,Math.min(16384,n));if($('lockRatio').checked&&key==='width')a.height=Math.max(1,Math.min(16384,a.height*n/a.width));if($('lockRatio').checked&&key==='height')a.width=Math.max(1,Math.min(16384,a.width*n/a.height));a[key]=n;dirty=true;updateFields();draw()};$(id).onblur=updateFields;}
$('textWidth').onpointerdown=()=>snapshot();$('textWidth').oninput=()=>{const a=current();if(!a?.text)return;const width=a.text.base_width||assetImages[a.asset]?.naturalWidth||a.width,height=a.text.base_height||assetImages[a.asset]?.naturalHeight||a.height;a.width=Math.max(1,Math.min(16384,a.height*width/height*Number($('textWidth').value)/100));dirty=true;updateFields();draw()};
for(const[id,key,factor]of[['rotation','rotation',1],['opacity','opacity',.01]]){$(id).onpointerdown=()=>snapshot();$(id).oninput=()=>{const a=current();if(a){a[key]=key==='rotation'?snapAngle(Number($(id).value),true):Number($(id).value)*factor;dirty=true;updateFields();draw()}}}
$('rotation').onchange=()=>{const a=current();if(a){a.rotation=snapAngle(a.rotation);updateFields();draw()}};
for(const[id,delta]of[['rotateLeft',-90],['rotateReset',null],['rotateRight',90]])$(id).onclick=()=>{const a=current();if(!a)return;snapshot();a.rotation=delta===null?0:((a.rotation+delta+540)%360)-180;updateFields();draw()};
function applyChosenColor(color){setColorInputs(color);const a=current(),ov=a&&currentOverlay(a);if(a&&ov?.mode==='solid'){snapshot();setOverlay(a,{...ov,color});rememberColor(color)}}
$('artColorPicker').oninput=()=>applyChosenColor(canonicalColor($('artColorPicker').value));
$('artColorHex').onchange=()=>{const color=canonicalColor($('artColorHex').value);if(color)applyChosenColor(color);else notify('Enter a six-digit HEX colour, like #E9FF57.',true)};
$('saveSwatch').onclick=()=>{const color=canonicalColor($('artColorHex').value);if(color)rememberColor(color);else notify('Enter a six-digit HEX colour, like #E9FF57.',true)};

$('removeWhite').onclick=async()=>{const art=current();if(!art)return;await busy('Removing white background',async()=>{const result=await(await api('artwork/remove-white',{asset:art.asset})).json();assetImages[result.id]=await imageLoad(url('artwork/'+result.id));snapshot();art.asset=result.id;art.name=result.name;renderArtList();draw()},'Keeping the artwork while making edge-connected white pixels transparent.')};
$('duplicate').onclick=()=>{const a=current();if(!a)return;snapshot();const b={...a,id:crypto.randomUUID(),x:a.x+50,y:a.y+50,name:a.name+' copy'};state.artworks.push(b);selected=b.id;renderArtList();draw()};
function removeArt(){if(!current())return;snapshot();state.artworks=state.artworks.filter(a=>a.id!==selected);selected=null;renderArtList();draw()}
$('deleteArt').onclick=removeArt;
for(const[id,delta]of[['sendBack',-1],['bringFront',1]])$(id).onclick=()=>moveArtwork(selected,delta);
function updateTabs(){document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);b.setAttribute('aria-selected',b.dataset.view===view?'true':'false')})}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=async()=>{view=b.dataset.view;updateTabs();if(view!=='default'&&!images[view])await busy('Opening '+view+' preview',async()=>{images[view]=await imageLoad(url(`preview/${view}?v=${Date.now()}`))},'The first map preview may take a moment.');draw()});
$('zoomIn').onclick=()=>{zoom=Math.min(8,zoom*1.2);draw()};$('zoomOut').onclick=()=>{zoom=Math.max(.2,zoom/1.2);draw()};$('fit').onclick=()=>{zoom=1;pan={x:0,y:0};draw()};
function mayReplace(){return !dirty||confirm('Open another file? Save your project first if you want to keep these changes.')}
for(const id of ['openPsd','startOpen'])$(id).onclick=()=>{if(mayReplace())$('psdInput').click()};
$('openProject').onclick=()=>{if(mayReplace())$('projectInput').click()};
for(const[id,path]of[['psdInput','open'],['projectInput','project/open']])$(id).onchange=async()=>{const file=$(id).files[0];if(!file)return;await busy('Opening your '+(path==='open'?'PSD':'project'),async()=>{const form=new FormData();form.append('file',file);await acceptDoc(await(await api(path,form)).json())});$(id).value=''};
$('addArtwork').onclick=()=>$('artInput').click();$('artInput').onchange=async()=>{await addFiles([...$('artInput').files]);$('artInput').value=''};$('pasteArtwork').onclick=nativePaste;
document.addEventListener('paste',e=>{if(/INPUT|TEXTAREA/.test(e.target.tagName)||!ready)return;e.preventDefault();nativePaste()});
$('stage').ondragover=e=>{e.preventDefault()};$('stage').ondrop=e=>{e.preventDefault();addFiles([...e.dataTransfer.files])};
document.addEventListener('keydown',e=>{if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();undoAction(e.shiftKey)}if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();removeArt()}if(current()&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();snapshot();const a=current(),step=e.shiftKey?10:1;a.x+=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0;a.y+=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;updateFields();draw()}});
async function saveDownload(path,title){await busy(title,async()=>{const r=await api(path,getState());if(r.headers.get('Content-Type')?.includes('application/json')){const result=await r.json();if(result.cancelled){notify('Save cancelled.');return}if(path==='project/save')dirty=false;notify('Saved '+result.filename);return}const blob=await r.blob();let name=r.headers.get('Content-Disposition')?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];if(name)name=decodeURIComponent(name);else name=r.headers.get('Content-Disposition')?.match(/filename="?([^";]+)"?/i)?.[1]||'Dirt Gear';const a=document.createElement('a');const src=URL.createObjectURL(blob);a.href=src;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(src),60000);if(path==='project/save')dirty=false;notify(`Saved ${name}. Check your Downloads folder.`)},'Rendering full-resolution textures and checking the output. This can take a minute.')}
$('saveForLater').onclick=()=>busy('Saving your editable design',async()=>{const result=await(await api('project/quick-save',getState())).json();dirty=false;notify(`Saved ${result.name}. You can continue it next time you open Dirt Gear.`);await loadRecentProject()},'Keeping your PSD, artwork, text, and layer choices together on this PC.');
let recentProject=null;
async function loadRecentProject(){const data=await(await api('project/recent',undefined,'GET')).json();recentProject=data.projects[0]||null;$('continueProject').hidden=!recentProject;if(recentProject)$('continueProject').textContent='Continue '+recentProject.name}
$('continueProject').onclick=async()=>{if(!recentProject||!mayReplace())return;await busy('Opening your saved design',async()=>{const data=await(await api('project/reopen',{id:recentProject.id})).json();await acceptDoc(data);dirty=false},'Restoring your PSD and editable artwork.');};
$('exportPnt').onclick=()=>saveDownload('export/pnt','Packing your MX Bikes paint');$('exportTga').onclick=()=>saveDownload('export/tga','Exporting your three textures');$('saveProject').onclick=()=>saveDownload('project/save','Saving your editable project');$('gearName').oninput=()=>dirty=true;
async function loadGameModels(){try{const data=await(await api('game/paint-folders',undefined,'GET')).json(),picker=$('gameModel');picker.replaceChildren();if(!data.models.length){picker.add(new Option('No MX Bikes rider models found',''));$('installPnt').disabled=true;return}for(const model of data.models)picker.add(new Option(model,model));picker.value=data.models.includes('default_mx')?'default_mx':data.models[0];$('installPnt').disabled=!ready}catch(e){notify('Could not find MX Bikes rider folders: '+e.message,true)}}
$('gameModel').onchange=()=>$('installPnt').disabled=!ready||!$('gameModel').value;
$('installPnt').onclick=async()=>{const model=$('gameModel').value;if(!model)return;await busy('Installing paint in MX Bikes',async()=>{let response=await(await api('game/install-pnt',{model,state:getState()})).json();if(response.exists){if(!confirm(`${response.filename} already exists for ${model}. Replace it?`))return;response=await(await api('game/install-pnt',{model,state:getState(),replace:true})).json()}notify(`Installed ${response.filename} for ${model}. Restart MX Bikes to refresh its paint list.`)},'Packing the textures and saving the paint into the selected rider model.');};
$('retryShading').onclick=()=>{proofFailedKey='';draw()};
$('proofBtn').onclick=async()=>{await busy('Checking final rendering',async()=>{await api('render',getState());$('proofImage').src=url('preview/proof?v='+Date.now());$('proofDialog').showModal()})};$('closeProof').onclick=()=>$('proofDialog').close();
$('busyDialog').addEventListener('cancel',e=>e.preventDefault());window.addEventListener('beforeunload',e=>{if(!desktop&&dirty){e.preventDefault();e.returnValue=''}});window.addEventListener('resize',resize);
(async()=>{try{const platform=await(await api('platform',undefined,'GET')).json();desktop=platform.desktop;appVersion=platform.version||'';$('versionBtn').textContent='v'+appVersion;$('aboutVersion').textContent=appVersion;setTimeout(()=>checkUpdates(false),4000);await loadGameModels();try{await loadRecentProject()}catch(e){notify('Saved projects are unavailable: '+e.message,true)}const data=await(await api('document',undefined,'GET')).json();if(data)await acceptDoc(data)}catch(e){notify(e.message,true)}})();
setInterval(()=>api('heartbeat',{}).catch(()=>{}),15000);
function defaultTextColour(){
 try{const im=images.default;if(!im)return '#202020';const c=document.createElement('canvas');c.width=c.height=9;const g=c.getContext('2d');g.drawImage(im,im.naturalWidth*.45,im.naturalHeight*.45,im.naturalWidth*.1,im.naturalHeight*.1,0,0,9,9);const p=g.getImageData(0,0,9,9).data;let light=0;for(let i=0;i<p.length;i+=4)light+=p[i]*.2126+p[i+1]*.7152+p[i+2]*.0722;return light/81>115?'#202020':'#ffffff'}catch{return '#202020'}
}
let fontPreviewTimer, fontPreviewVersion=0, fontPreviewUrl=null;
function textSettings(){return {value:$('textValue').value,font:$('fontSelect').value,size:Number($('fontSize').value),tracking:Number($('textTracking').value),fill:$('textFill').value,stroke:Number($('textStroke').value),outline:$('textOutline').value,gradient:$('useGradient').checked?{start:$('gradientStart').value,end:$('gradientEnd').value,angle:Number($('gradientAngle').value)}:null}}
function clearFontPreview(){
 clearTimeout(fontPreviewTimer);fontPreviewVersion++;
 $('fontPreviewImage').hidden=true;$('fontPreviewImage').removeAttribute('src');
 if(fontPreviewUrl){URL.revokeObjectURL(fontPreviewUrl);fontPreviewUrl=null}
}
function queueFontPreview(){
 $('gradientOptions').hidden=!$('useGradient').checked;
 clearFontPreview();const version=fontPreviewVersion,settings=textSettings();
 const status=$('fontPreviewStatus');status.hidden=false;
 if(!settings.value.trim()){status.textContent='Type a name or number to preview';return}
 status.textContent='Rendering preview…';
 fontPreviewTimer=setTimeout(async()=>{
  try{
   const response=await api('text/preview',settings),blob=await response.blob();
   if(version!==fontPreviewVersion||!$('textDialog').open)return;
   const src=URL.createObjectURL(blob);
   try{await imageLoad(src)}catch(e){URL.revokeObjectURL(src);throw e}
   if(version!==fontPreviewVersion||!$('textDialog').open){URL.revokeObjectURL(src);return}
   fontPreviewUrl=src;$('fontPreviewImage').src=src;$('fontPreviewImage').alt=settings.value+' — '+$('fontSelect').selectedOptions[0].textContent;
   $('fontPreviewImage').hidden=false;status.hidden=true;
  }catch(e){if(version===fontPreviewVersion){status.textContent=e.message;status.hidden=false}}
 },150);
}
for(const id of ['textValue','fontSelect','fontSize','textTracking','textFill','textStroke','textOutline','useGradient','gradientStart','gradientEnd','gradientAngle'])$(id).addEventListener('input',queueFontPreview);
$('textDialog').addEventListener('close',clearFontPreview);
async function showText(kind='name',edit=false){
 try{if(!fonts.length)fonts=await(await api('fonts',undefined,'GET')).json();
 const picker=$('fontSelect');picker.replaceChildren();for(const f of fonts)picker.add(new Option((f.byd?'BYD / ':f.mx?'MX / ':'')+f.label,f.id));
 const a=edit?current():null;editingText=a?.id||null;
 const preferred=fonts.find(f=>f.id.toLowerCase().includes(`byd-${kind==='number'?'number':'name'}-font-stock`))||fonts.find(f=>/arialbd/i.test(f.id))||fonts[0];
 const t=a?.text||{value:kind==='number'?'76':'YOUR NAME',font:preferred?.id,size:kind==='number'?500:240,fill:defaultTextColour(),stroke:0,outline:'#000000'};
 $('textValue').value=t.value;picker.value=t.font;if(!picker.value&&preferred)picker.value=preferred.id;
 $('fontSize').value=t.size;$('textTracking').value=t.tracking||0;$('trackingValue').textContent=(t.tracking||0)+'%';$('textFill').value=t.fill;$('textStroke').value=t.stroke;$('textOutline').value=t.outline;$('useGradient').checked=!!t.gradient;$('gradientStart').value=t.gradient?.start||t.fill;$('gradientEnd').value=t.gradient?.end||'#ffffff';$('gradientAngle').value=String(t.gradient?.angle??90);
 $('textTitle').textContent=edit?'Edit your rider details.':kind==='number'?'Add your race number.':'Add your name.';$('applyText').textContent=edit?'Update text':'Add to gear';renderSwatches();$('textDialog').showModal();queueFontPreview();
 }catch(e){notify(e.message,true)}
}
$('addName').onclick=()=>showText('name');$('addNumber').onclick=()=>showText('number');$('editText').onclick=()=>showText('name',true);
$('applyText').onclick=async()=>{const settings={value:$('textValue').value,font:$('fontSelect').value,size:Number($('fontSize').value),tracking:Number($('textTracking').value),fill:$('textFill').value,stroke:Number($('textStroke').value),outline:$('textOutline').value,gradient:$('useGradient').checked?{start:$('gradientStart').value,end:$('gradientEnd').value,angle:Number($('gradientAngle').value)}:null};if(!settings.value.trim()){notify('Enter a name or number.',true);return}
 $('textDialog').close();await busy('Creating your text',async()=>{const item=await(await api('text',settings)).json();const old=state.artworks.find(a=>a.id===editingText);if(old){snapshot();const previousWidth=old.text?.base_width||assetImages[old.asset]?.naturalWidth||old.width,previousHeight=old.text?.base_height||assetImages[old.asset]?.naturalHeight||old.height;const widthScale=old.width/previousWidth,heightScale=old.height/previousHeight;assetImages[item.id]=await imageLoad(url('artwork/'+item.id));old.asset=item.id;old.name=item.name;old.text=item.text;old.width=Math.max(1,Math.min(16384,item.width*widthScale));old.height=Math.max(1,Math.min(16384,item.height*heightScale));selected=old.id;}else{await addAsset(item);const art=current();art.text=item.text;art.width=item.width;art.height=item.height;}
 rememberColor(settings.fill);if(settings.gradient){rememberColor(settings.gradient.start);rememberColor(settings.gradient.end)}if(settings.stroke>0)rememberColor(settings.outline);lastFieldSelection=null;renderArtList();draw();},'Rendering your selected font locally.');};


let sampleTarget=null;
for(const button of document.querySelectorAll('[data-sample]'))button.onclick=()=>{
 sampleTarget=button.dataset.sample;$('textDialog').close();view='default';updateTabs();draw();document.body.classList.add('sampling');notify('Click a colour on the gear. Press Escape to cancel.');
};
canvas.addEventListener('pointerdown',async e=>{
 if(!sampleTarget)return;e.preventDefault();e.stopImmediatePropagation();
 const p=point(e);if(p.x<0||p.y<0||p.x>=doc.width||p.y>=doc.height)return;
 const target=sampleTarget;
 try{const result=await(await api('sample-colour',{x:Math.floor(p.x),y:Math.floor(p.y)})).json();
 if(sampleTarget!==target)return;$(target).value=result.colour;rememberColor(result.colour);finishSampling();
 }catch(err){notify(err.message,true);if(sampleTarget)finishSampling()}

},true);
let sampleReturn='text';
function finishSampling(){const back=sampleReturn;sampleTarget=null;sampleReturn='text';document.body.classList.remove('sampling');if(back==='overlay'){overlayFromInputs(true);return}$('textDialog').showModal();queueFontPreview()}
document.addEventListener('keydown',e=>{if(sampleTarget&&e.key==='Escape'){e.preventDefault();finishSampling()}},true);
$('saveLogo').onclick=async()=>{const art=current();if(!art)return;try{await api('logos',{asset:art.asset,name:art.name,overlay:currentOverlay(art)});notify('Saved to your logo library. Open Saved logos in any project to reuse it.')}catch(e){notify(e.message,true)}};
async function renderLogoLibrary(){
 const logos=await(await api('logos',undefined,'GET')).json(),list=$('logoLibrary');list.replaceChildren();
 if(!logos.length)list.textContent='Select an added logo and choose Save to logo library.';
 for(const logo of logos){
  const card=document.createElement('div');card.className='saved-logo';
  const button=document.createElement('button'),image=document.createElement('img'),name=document.createElement('span');
  button.className='use-logo';image.src=url('logos/'+logo.id+'/image');image.alt='';name.textContent=logo.name;
  button.title='Add '+logo.name;button.append(image,name);
  button.onclick=async()=>{$('logoDialog').close();await busy('Adding saved logo',async()=>{await addAsset(await(await api('logos/'+logo.id+'/add',{})).json())})};
  const remove=document.createElement('button');remove.className='delete-logo danger';remove.textContent='Delete';remove.setAttribute('aria-label','Delete '+logo.name);
  remove.onclick=async()=>{if(!confirm('Delete "'+logo.name+'" from saved logos? Artwork already added to projects will stay.'))return;
   remove.disabled=true;try{await api('logos/'+logo.id,undefined,'DELETE');await renderLogoLibrary();notify('Removed from saved logos.')}catch(e){remove.disabled=false;notify(e.message,true)}
  };
  card.append(button,remove);list.append(card);
 }
}
$('openLogoLibrary').onclick=async()=>{try{await renderLogoLibrary();$('logoDialog').showModal()}catch(e){notify(e.message,true)}};
$('closeLogos').onclick=()=>$('logoDialog').close();
let riderViewer=null;
$('open3d').onclick=async()=>{
 if(!ready)return;$('viewerDialog').showModal();$('viewerStatus').textContent='Preparing your gear…';
 try{
  if(!riderViewer)riderViewer=await DirtRider.create($('riderCanvas'));
  riderViewer.resize();
  const epoch=previewEpoch;const diffuse=URL.createObjectURL(await(await api('viewer/diffuse',getState())).blob());
  const stamp=Date.now();const [texture,normal,reflection]=await Promise.all([imageLoad(diffuse).finally(()=>setTimeout(()=>URL.revokeObjectURL(diffuse),1000)),imageLoad(url('viewer/map/normal?v='+stamp)),imageLoad(url('viewer/map/spec?v='+stamp))]);
  if(epoch!==previewEpoch||!$('viewerDialog').open)return;
  riderViewer.setTextures(texture,normal,reflection);riderViewer.setMaps($('riderNormals').checked,$('riderReflections').checked);$('viewerStatus').textContent='Your current design · '+(state.normal_layers.length?'Normal map':'No Normal map')+' · '+(state.spec?'Reflection map':'No Reflection map (matte)');
 }catch(e){$('viewerStatus').textContent='Could not open preview: '+e.message}
};
$('close3d').onclick=()=>$('viewerDialog').close();
$('riderFront').onclick=()=>riderViewer?.setView(0);
$('riderBack').onclick=()=>riderViewer?.setView(Math.PI);
$('riderReset').onclick=()=>riderViewer?.reset();
window.addEventListener('resize',()=>{if($('viewerDialog').open)riderViewer?.resize()});

$('riderPan').onclick=()=>{const active=$('riderPan').getAttribute('aria-pressed')!=='true';$('riderPan').setAttribute('aria-pressed',String(active));riderViewer?.setPanMode(active)};
$('riderUp').onclick=()=>riderViewer?.pan(0,.25);$('riderDown').onclick=()=>riderViewer?.pan(0,-.25);

for(const id of ['riderNormals','riderReflections'])$(id).onchange=()=>riderViewer?.setMaps($('riderNormals').checked,$('riderReflections').checked);

function renderGradientSwatches(){
 for(const target of ['gradientStart','gradientEnd']){
  const box=$(target+'Swatches');box.replaceChildren();
  for(const color of state?.palette||[]){const b=document.createElement('button');b.type='button';b.className='swatch';b.style.background=color;b.title=color;b.setAttribute('aria-label','Use '+color+' for '+(target==='gradientStart'?'start':'end'));
   b.onclick=()=>{$(target).value=color.toLowerCase();queueFontPreview()};box.append(b)}
  if(!box.children.length){const t=document.createElement('small');t.textContent='Your saved colours will appear here.';box.append(t)}
 }
}
async function renderLayouts(){
 const items=await(await api('layouts',undefined,'GET')).json(),box=$('layoutLibrary');box.replaceChildren();
 if(!items.length)box.textContent='No saved layouts yet.';
 for(const item of items){
  const row=document.createElement('div');row.className='layout-row';const name=document.createElement('span');name.textContent=item.name+' · '+item.count+' layers';
  const apply=document.createElement('button');apply.textContent='Apply';apply.onclick=async()=>{
   if(state.artworks.length+item.count>100){notify('This would exceed the 100 added-layer limit.',true);return}
   $('layoutDialog').close();await busy('Applying logo layout',async()=>{
    const result=await(await api('layouts/'+item.id+'/add',{})).json();
    const loaded=await Promise.all(result.assets.map(async a=>[a.id,await imageLoad(url('artwork/'+a.id))]));
    snapshot();for(const [id,image] of loaded)assetImages[id]=image;
    state.artworks.push(...result.artworks);state.palette=[...new Set([...(state.palette||[]),...result.palette])].slice(0,32);storePalette();
    selected=result.artworks.at(-1)?.id;view='default';updateTabs();renderArtList();renderSwatches();draw();notify('Layout applied. Check placement on the new gear before exporting.');
   },'Keeping your artwork editable and scaling positions to this template.');
  };
  const remove=document.createElement('button');remove.textContent='Delete';remove.className='danger';remove.onclick=async()=>{if(!confirm('Delete saved layout "'+item.name+'"? Existing projects will stay.'))return;try{await api('layouts/'+item.id,undefined,'DELETE');await renderLayouts()}catch(e){notify(e.message,true)}};
  row.append(name,apply,remove);box.append(row);
 }
}
$('openLayouts').onclick=async()=>{try{$('layoutName').value=$('gearName').value||'My logo layout';await renderLayouts();$('layoutDialog').showModal()}catch(e){notify(e.message,true)}};
$('closeLayouts').onclick=()=>$('layoutDialog').close();
$('saveLayout').onclick=async()=>{const button=$('saveLayout');button.disabled=true;try{await api('layouts',{name:$('layoutName').value,state:getState()});await renderLayouts();notify('Layout saved. Open another gear PSD and use Logo layouts → Apply.')}catch(e){notify(e.message,true)}finally{button.disabled=false}};

// ── Updates (same flow as Optic and Moto Lines Studio) ──
let appVersion='',updateInfo=null;
function noteText(notes){return (notes||'').replace(/^#+\s*/gm,'').trim()||'See the release page for details.'}
function showUpdate(info){
 updateInfo=info;const ready=!!(info&&info.available);document.body.classList.toggle('update-ready',ready);
 const show=ready&&!info.skipped&&!sessionStorageGet('dgHideUpdate'+info.latest);
 $('updateBar').hidden=!show;document.body.classList.toggle('update-shown',show);
 if(ready){
  $('updateText').innerHTML='';const b=document.createElement('strong');b.textContent='Dirt Gear '+info.latest;$('updateText').append(b,' is available');
  const label=info.can_install?'Download and install':'Open download page';$('updateInstall').textContent=label;$('aboutInstall').textContent=label;
  $('aboutLatest').textContent=info.latest;$('aboutNotes').textContent=noteText(info.notes);
 }
 $('aboutNotesWrap').hidden=!ready;$('aboutInstall').hidden=!ready;
 if(info)$('checkOnStart').checked=info.check_on_start!==false;
 if(show)resize();
}
function sessionStorageGet(k){try{return sessionStorage.getItem(k)}catch{return null}}
function sessionStorageSet(k,v){try{sessionStorage.setItem(k,v)}catch{}}
async function checkUpdates(manual){
 try{
  if(manual)$('updateStatus').textContent='Checking GitHub…';
  const info=await(await api('update/check'+(manual?'?manual=1':''),undefined,'GET')).json();
  showUpdate(info);
  if(manual)$('updateStatus').textContent=!info.enabled?'This copy wasn’t installed from a Dirt Gear release, so it doesn’t check for updates.':info.error?info.error:info.available?`Dirt Gear ${info.latest} is available. You have ${info.current}.`+(info.can_install?'':' This release opens its download page.'):`You’re up to date (${info.current}).`;
 }catch(e){if(manual)$('updateStatus').textContent='Could not check for updates: '+e.message}
}
async function installUpdate(){
 if(!updateInfo?.available)return;
 if(!updateInfo.can_install){try{await api('update/open-page',{})}catch(e){notify(e.message,true)}return}
 if(dirty&&!confirm('Dirt Gear restarts to update. Unsaved changes to this design will be lost — choose Cancel to save first.'))return;
 $('aboutDialog').close();
 const ok=await busy('Downloading Dirt Gear '+updateInfo.latest,async()=>{await api('update/install',{});return true},'Checking the download’s signature, then the installer takes over.');
 if(ok){dirty=false;$('busyTitle').textContent='Installing update…';$('busyDetail').textContent='Dirt Gear will close and reopen in a moment.';$('busyDialog').showModal()}
}
$('updateInstall').onclick=installUpdate;$('aboutInstall').onclick=installUpdate;
$('updateSkip').onclick=async()=>{if(!updateInfo)return;try{await api('update/settings',{skip_version:updateInfo.latest});updateInfo.skipped=true;showUpdate(updateInfo);notify('Skipped '+updateInfo.latest+'. Check for updates from the version button any time.')}catch(e){notify(e.message,true)}};
$('updateClose').onclick=()=>{if(updateInfo)sessionStorageSet('dgHideUpdate'+updateInfo.latest,'1');showUpdate(updateInfo)};
$('updateNotes').onclick=()=>{$('aboutDialog').showModal()};
$('versionBtn').onclick=()=>{$('aboutDialog').showModal();checkUpdates(true)};
$('closeAbout').onclick=()=>$('aboutDialog').close();
$('checkNow').onclick=()=>checkUpdates(true);
$('checkOnStart').onchange=async()=>{try{await api('update/settings',{check_on_start:$('checkOnStart').checked})}catch(e){notify(e.message,true)}};

$('textTracking').addEventListener('input',()=>{$('trackingValue').textContent=$('textTracking').value+'%'});
$('textTracking').addEventListener('dblclick',()=>{$('textTracking').value=0;$('trackingValue').textContent='0%';queueFontPreview()});

// ── Colour overlay for added logos (solid colour or gradient) ──
function currentOverlay(a){return a?.overlay||(a?.color?{mode:'solid',color:a.color,strength:1}:null)}
function setOverlay(a,ov){if(ov){a.overlay=ov;delete a.color}else{delete a.overlay;delete a.color}dirty=true;updateOverlayUI(a);draw()}
function overlayMode(){return document.querySelector('#overlayMode .active')?.dataset.ov||'off'}
function updateOverlayUI(a){
 $('overlayBox').hidden=!!a.text;const ov=currentOverlay(a),mode=ov?.mode||'off';
 document.querySelectorAll('#overlayMode button').forEach(b=>b.classList.toggle('active',b.dataset.ov===mode));
 $('ovSolid').hidden=mode!=='solid';$('ovGradient').hidden=mode!=='gradient';$('ovStrengthLabel').hidden=mode==='off';
 if(ov){if(ov.color)$('ovColor').value=ov.color.toLowerCase();if(ov.start)$('ovStart').value=ov.start.toLowerCase();if(ov.end)$('ovEnd').value=ov.end.toLowerCase();$('ovAngle').value=String(ov.angle??90);const st=Math.round((ov.strength??1)*100);$('ovStrength').value=st;$('ovStrengthValue').textContent=st+'%'}
 renderOverlaySwatches();
}
function overlayFromInputs(record){const a=current();if(!a)return;const mode=overlayMode(),strength=Number($('ovStrength').value)/100;
 if(record)snapshot();
 if(mode==='off')setOverlay(a,null);
 else if(mode==='solid')setOverlay(a,{mode,color:$('ovColor').value.toUpperCase(),strength});
 else setOverlay(a,{mode,start:$('ovStart').value.toUpperCase(),end:$('ovEnd').value.toUpperCase(),angle:Number($('ovAngle').value),strength});
}
document.querySelectorAll('#overlayMode button').forEach(b=>b.onclick=()=>{const a=current();if(!a)return;document.querySelectorAll('#overlayMode button').forEach(x=>x.classList.toggle('active',x===b));
 if(b.dataset.ov==='solid'&&!currentOverlay(a))$('ovColor').value=(state.palette?.[0]||'#FFFFFF').toLowerCase();
 if(b.dataset.ov==='gradient'&&!currentOverlay(a)?.start){$('ovStart').value=(state.palette?.[0]||'#FF4020').toLowerCase();$('ovEnd').value=(state.palette?.[1]||'#FFD020').toLowerCase()}
 overlayFromInputs(true)});
let ovTouched=false;
for(const id of ['ovColor','ovStart','ovEnd','ovStrength']){$(id).addEventListener('pointerdown',()=>{snapshot();ovTouched=true});$(id).addEventListener('input',()=>{if(!ovTouched){snapshot();ovTouched=true}if(id==='ovStrength')$('ovStrengthValue').textContent=$('ovStrength').value+'%';overlayFromInputs(false)});$(id).addEventListener('change',()=>{ovTouched=false;if(id!=='ovStrength')rememberColor($(id).value)})}
$('ovAngle').onchange=()=>overlayFromInputs(true);
$('ovSwap').onclick=()=>{const t=$('ovStart').value;$('ovStart').value=$('ovEnd').value;$('ovEnd').value=t;overlayFromInputs(true)};
for(const b of document.querySelectorAll('[data-ovpick]'))b.onclick=()=>{if(!current())return;sampleTarget=b.dataset.ovpick;sampleReturn='overlay';view='default';updateTabs();draw();document.body.classList.add('sampling');notify('Click a colour on the gear. Press Escape to cancel.')};
function renderOverlaySwatches(){for(const [box,input] of [['ovColorSwatches','ovColor'],['ovStartSwatches','ovStart'],['ovEndSwatches','ovEnd']]){const el=$(box);el.replaceChildren();for(const color of state?.palette||[]){const b=document.createElement('button');b.type='button';b.className='swatch';b.style.background=color;b.title=color;b.setAttribute('aria-label','Use '+color);b.onclick=()=>{$(input).value=color.toLowerCase();overlayFromInputs(true)};el.append(b)}if(!el.children.length){const t=document.createElement('small');t.textContent='Saved colours appear here.';t.className='hint';el.append(t)}}}

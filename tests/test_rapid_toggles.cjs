const {chromium}=require('playwright');const fs=require('fs');
const SP=process.argv[2],PSD=process.argv[3];const s=JSON.parse(fs.readFileSync(SP+'/session.json'));
const ok=(c,m)=>{if(!c)throw Error('FAIL '+m);console.log('PASS',m)};
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1500,height:920}});
const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.goto(s.url);let t=Date.now();
await p.setInputFiles('#psdInput',PSD);
await p.waitForFunction(()=>ready&&images.default&&!document.getElementById('busyDialog').open,null,{timeout:300000});
console.log('open + first preview',(Date.now()-t)/1000,'s');
// add a name so artwork/shading path is exercised
await p.click('#addName');await p.waitForSelector('#textDialog[open]');await p.fill('#textValue','JEFFERY');await p.click('#applyText');
await p.waitForFunction(()=>!document.getElementById('busyDialog').open,null,{timeout:60000});
const row=name=>p.locator('.layer',{has:p.locator(`label:text-is("${name}")`)}).locator('input[type=checkbox]');
const settle=async()=>{for(let i=0;i<3;i++){await p.waitForTimeout(500);await p.waitForFunction(()=>!visBusy&&!visTimer&&!proofBusy&&!proofTimer,null,{timeout:120000})}};
const mean=async()=>p.evaluate(()=>{const c=document.getElementById('canvas');const g=document.createElement('canvas');g.width=200;g.height=200;const x=g.getContext('2d');x.drawImage(c,0,0,200,200);const d=x.getImageData(0,0,200,200).data;let s=0;for(let i=0;i<d.length;i+=4)s+=d[i]+d[i+1]+d[i+2];return s/(d.length/4)/3});
await settle();const m0=await mean();
// rapid clicks like a real user
t=Date.now();
await row('X').click();await row('Honda').click();await row('UV').click();await row('UV').click();await row('X').click();await row('X').click();
await settle();console.log('6 rapid clicks settled in',(Date.now()-t)/1000,'s');
const st=await p.evaluate(()=>{const v=state.visibility,n={};for(const l of doc.layers)n[l.name+'#'+l.id]=v[l.id];return n});
ok(st['X#8']===false&&st['Honda#1.3']===false&&st['UV#7']===false,'client state after clicks: X off, Honda off, UV off');
const srv=await p.evaluate(async()=>(await (await fetch('/api/document?token='+token)).json()).state.visibility);
ok(srv['8']===false&&srv['1.3']===false&&srv['7']===false,'server state matches the panel');
const m1=await mean();ok(m1>5,'canvas is drawn, not blank (mean '+m1.toFixed(1)+')');
console.log('status:',await p.textContent('#canvasStatus'));ok(await p.evaluate(()=>proofKey===previewKey()),'shown preview is the shaded render for the current layers');
await p.screenshot({path:SP+'/shots/real-after-toggles.png'});
// toggle Honda back on: Navy hidden under it again
await row('Honda').click();await settle();await p.screenshot({path:SP+'/shots/real-honda-on.png'});
ok(errs.length===0,'no page errors '+JSON.stringify(errs));await b.close()})().catch(e=>{console.error(e.message);process.exit(1)});

const {chromium}=require('playwright');const fs=require('fs');
const SP=process.argv[2];const s=JSON.parse(fs.readFileSync(SP+'/session.json'));
const ok=(c,m)=>{if(!c)throw Error('FAIL '+m);console.log('PASS',m)};
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1500,height:920}});
const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('dialog',d=>d.accept());
const idle=()=>p.waitForFunction(()=>!document.getElementById('busyDialog').open,{timeout:60000});
await p.goto(s.url);await p.waitForTimeout(800);
await p.setInputFiles('#psdInput',SP+'/fixtures/test-gear.psd');await p.waitForSelector('#canvas:not([hidden])',{timeout:60000});await idle();
// save two colours in the palette
await p.click('.palette-panel summary');
for(const c of ['#E91E63','#00BCD4']){await p.fill('#artColorHex',c);await p.click('#saveSwatch')}
ok(await p.locator('#swatches .swatch').count()>=2,'saved colours added to palette');
// gradient name using saved swatches for each stop independently
await p.click('#addName');await p.waitForSelector('#textDialog[open]');await p.fill('#textValue','KTIP');await p.check('#useGradient');
const startSw=p.locator('#gradientStartSwatches .swatch'),endSw=p.locator('#gradientEndSwatches .swatch');
ok(await startSw.count()>=2&&await endSw.count()>=2,'saved colours shown under both gradient stops');
await startSw.filter({has:p.locator('xpath=.')}).nth(0);
await p.locator('#gradientStartSwatches .swatch[title="#00BCD4"]').click();await p.locator('#gradientEndSwatches .swatch[title="#E91E63"]').click();
ok(await p.inputValue('#gradientStart')==='#00bcd4'&&await p.inputValue('#gradientEnd')==='#e91e63','start and end set independently from saved colours');
await p.waitForTimeout(1200);await p.screenshot({path:SP+'/shots/DirtGear-gradient-swatches.png'});
await p.click('#applyText');await idle();await p.waitForTimeout(1500);
// add a number too
await p.click('#addNumber');await p.waitForSelector('#textDialog[open]');await p.click('#applyText');await idle();await p.waitForTimeout(800);
const before=await p.evaluate(()=>state.artworks.map(a=>({x:a.x,w:a.width,g:a.text?.gradient})));
ok(before.length===2&&before.some(a=>a.g&&a.g.start==='#00bcd4'),'two layers, gradient stored on name');
// save layout
await p.click('#openLayouts');await p.waitForSelector('#layoutDialog[open]');await p.fill('#layoutName','KTip race layout');await p.click('#saveLayout');
await p.waitForSelector('.layout-row');await p.waitForTimeout(400);await p.screenshot({path:SP+'/shots/DirtGear-layouts.png'});
ok((await p.textContent('#layoutLibrary')).includes('KTip race layout · 2 layers'),'layout saved and listed');
await p.click('#closeLayouts');
// open a different gear (2048px) and apply
await p.setInputFiles('#psdInput',SP+'/fixtures/second-gear.psd');await p.waitForFunction(()=>doc&&doc.width===2048&&ready,{timeout:60000});await idle();
ok(await p.evaluate(()=>state.artworks.length)===0,'second gear opened empty');
await p.click('#openLayouts');await p.waitForSelector('.layout-row');
await p.locator('.layout-row',{hasText:'KTip race layout'}).locator('button',{hasText:'Apply'}).click();await idle();await p.waitForTimeout(2500);
const after=await p.evaluate(()=>state.artworks.map(a=>({x:a.x,w:a.width,g:a.text?.gradient})));
ok(after.length===2,'layout applied: 2 layers on new gear');
ok(Math.abs(after[0].x-before[0].x*2)<1&&Math.abs(after[0].w-before[0].w*2)<1,'positions/sizes scaled 1024→2048');
ok(after.some(a=>a.g&&a.g.start==='#00bcd4'&&a.g.end==='#e91e63'),'gradient text kept editable after transfer');
await p.screenshot({path:SP+'/shots/DirtGear-layout-applied.png'});
await p.keyboard.press('Control+z');await p.waitForTimeout(300);
ok(await p.evaluate(()=>state.artworks.length)===0,'one undo removes the applied layout');
ok(errs.length===0,'no page errors '+JSON.stringify(errs));
await b.close()})().catch(e=>{console.error(e.message);process.exit(1)});

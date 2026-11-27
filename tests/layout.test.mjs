import {demoUrl,openPage} from './lib.mjs';

export default async function run(browser){
 const lines=[],errors=[];
 const check=(name,got,want)=>lines.push(JSON.stringify(got)===JSON.stringify(want)?`ok   ${name}`:`FAIL ${name}: expected ${JSON.stringify(want)} got ${JSON.stringify(got)}`);
 for(const width of [280,390,760,1280]){
  const page=await openPage(browser,demoUrl,{viewport:{width,height:900}});
  await page.locator('mousetrap-manager-card img').evaluateAll(imgs=>Promise.all(imgs.map(i=>{i.loading="eager";return i.decode();})));
  for(const dark of [false,true]){
   if(dark)await page.locator('main>button').click();
   const view=await page.locator('mousetrap-manager-card').evaluate(c=>{
    const root=c.shadowRoot,tiles=Array.from(root.querySelectorAll('.tile'));
    return {overflow:document.documentElement.scrollWidth>innerWidth,tiles:tiles.length,overflowTiles:tiles.some(t=>t.scrollWidth>t.clientWidth),loaded:Array.from(root.querySelectorAll('img')).every(i=>i.naturalWidth>0),status:Array.from(root.querySelectorAll('.status')).map(e=>e.textContent)};
   });
   const label=`${width}px ${dark?'dark':'light'}`;
   check(`${label} has no page overflow`,view.overflow,false);
   check(`${label} has no tile overflow`,view.overflowTiles,false);
   check(`${label} displays eight traps`,view.tiles,8);
   check(`${label} images load`,view.loaded,true);
   check(`${label} has distinct source outage`,view.status[5],'Utilgjengelig');
  }
  errors.push(...page.errors);await page.close();
 }
 return {lines,errors};
}

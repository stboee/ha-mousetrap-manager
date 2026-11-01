import {fixtureUrl,openPage} from './lib.mjs';

export default async function run(browser){
 const page=await openPage(browser,fixtureUrl,{viewport:{width:390,height:844}});
 const lines=await page.evaluate(async()=>{
  const out=[],check=(name,got,want)=>out.push(JSON.stringify(got)===JSON.stringify(want)?`ok   ${name}`:`FAIL ${name}: expected ${JSON.stringify(want)} got ${JSON.stringify(got)}`);
  const st=(state,attributes)=>({state,attributes});
  const item=(name,text,color)=>({name,reason_text:text,color,icon:'mdi:rodent'});
  const attrs={mousetrap_manager_attention:true,schema_version:1,title:'Musefeller',count:2,summary:'2 feller trenger tilsyn',navigation_path:'/dashboard-hjem/musefeller',items:[item('Garasje1','Fangst meldt','#c51f3b'),item('Loft','Inspeksjon nødvendig · Lavt batteri','#986000')]};
  let wsCalls=0,serviceCalls=0;
  const hass={states:{'binary_sensor.renamed_attention':st('on',attrs)},callWS:async()=>{wsCalls++;},callService:async()=>{serviceCalls++;}};
  const card=document.createElement('mousetrap-manager-card');
  card.setConfig({type:'custom:mousetrap-manager-card',mode:'attention'});document.body.append(card);card.hass=hass;
  const q=s=>card.shadowRoot.querySelector(s),qa=s=>Array.from(card.shadowRoot.querySelectorAll(s));
  const update=(value,attributes=attrs)=>{hass.states={'binary_sensor.renamed_attention':st(value,attributes)};card.hass={...hass};};
  check('compact card does not steal keyboard focus on load',card.shadowRoot.activeElement,null);
  check('compact mode works from central entity alone',qa('.attention-row').length,2);
  check('server title and summary are displayed',[q('.attention-card h2').textContent,q('.attention-summary').textContent],['Musefeller','2 feller trenger tilsyn']);
  check('row order comes from server',qa('.attention-name').map(e=>e.textContent),['Garasje1','Loft']);
  check('all reasons remain on one row',q('.attention-items li:last-child .attention-reason').textContent,'Inspeksjon nødvendig · Lavt batteri');
  check('full illustration and journal view is hidden',q('.full-card').hidden,true);
  check('compact mode makes no journal request',wsCalls,0);
  check('compact mode sends no catch or maintenance action',serviceCalls,0);
  check('whole compact card links to configured HA view',q('.attention-link').getAttribute('href'),'/dashboard-hjem/musefeller');
  check('compact link supports keyboard navigation',q('.attention-link').tabIndex,0);
  check('compact card fits masonry column',q('.attention-card').getBoundingClientRect().right<=window.innerWidth,true);
  check('two affected traps make a compact card',q('.attention-card').getBoundingClientRect().height<300,true);
  q('.attention-link').focus();const link=q('.attention-link');card.hass={...hass};
  check('unrelated HA updates preserve link element and keyboard focus',q('.attention-link')===link && card.shadowRoot.activeElement===link,true);
  update('off',{...attrs,count:0,summary:'Ingen feller trenger tilsyn',items:[]});
  check('normal server status stays available when native visibility is disabled',getComputedStyle(card).display!=='none',true);
  check('normal status has no affected rows',qa('.attention-row').length,0);
  card.preview=true;
  check('normal preview remains editable',getComputedStyle(card).display!=='none',true);
  check('normal preview shows real server status',q('.attention-summary').textContent,'Ingen feller trenger tilsyn');
  card.preview=false;
  for(const value of ['unavailable','unknown']){
   update(value);
   check(`${value} never reuses stale affected trap rows`,qa('.attention-row').length,0);
   check(`${value} stays visible`,getComputedStyle(card).display!=='none',true);
   check(`${value} displays a status error`,!!q('.attention-error[role="status"]'),true);
  }
  hass.states={};card.hass={...hass};
  check('missing central entity is a visible error',!!q('.attention-error'),true);
  update('off',{...attrs,restored:true});
  check('restored off state cannot hide current unknown status',getComputedStyle(card).display!=='none',true);
  update('on',{...attrs,schema_version:999});
  check('unknown protocol shows error rather than inventing status',!!q('.attention-error'),true);
  update('on',{...attrs,items:[null]});
  check('invalid payload stays visible without throwing',!!q('.attention-error'),true);
  update('on',{...attrs,title:'<img src=x onerror=alert(1)>',items:[item('<b>Garasje</b>','<script>alert(1)</script>','#986000')]});
  check('server names and prose are escaped',q('.attention-card img,.attention-card script,.attention-name b'),null);
  for(const path of ['javascript:alert(1)','//example.com','/\\example.com']){
   update('on',{...attrs,navigation_path:path});check(`invalid navigation ${path} is inactive`,q('.attention-link'),null);
  }
  update('on',{...attrs,navigation_path:''});
  check('missing target explains where to configure navigation',q('.attention-hint').textContent.includes('Tilsynsvisning'),true);
  const Editor=customElements.get('mousetrap-manager-card').getConfigElement();
  const userCondition={condition:'user',users:['user-1']};
  Editor.setConfig({type:'custom:mousetrap-manager-card',grid_options:{columns:'full'},visibility:[userCondition]});
  Editor.hass={...hass,states:{'binary_sensor.renamed_attention':st('on',attrs)}};
  let config;
  Editor.addEventListener('config-changed',e=>{config=e.detail.config;});
  let select=Editor.shadowRoot.querySelector('select');select.value='attention';select.dispatchEvent(new Event('change'));
  const focusedSelect=Editor.shadowRoot.querySelector('select');focusedSelect.focus();Editor.hass={...Editor._hass};
  check('unrelated HA updates preserve editor controls',Editor.shadowRoot.querySelector('select')===focusedSelect,true);
  check('editor selects compact mode' ,config.mode,'attention');
  check('editor preserves HA layout settings',config.grid_options,{columns:'full'});
  check('editor preserves unrelated visibility condition',config.visibility[0],userCondition);
  check('editor automatically sets native visibility for actual entity ID',config.visibility[1],{condition:'state',entity:'binary_sensor.renamed_attention',state_not:'off'});
  check('editor uses not off so unknown and unavailable stay visible',config.visibility[1].state_not,'off');
  check('version is visible in editor',Editor.shadowRoot.textContent.includes('v0.4.0'),true);
  check('version can be queried for cache diagnosis',customElements.get('mousetrap-manager-card').getVersion(),'0.4.0');
  select=Editor.shadowRoot.querySelector('select');select.value='full';select.dispatchEvent(new Event('change'));
  check('switching to full mode preserves other visibility rules',config.visibility,[userCondition]);
  Editor.hass={states:{}};
  check('editor does not invent an entity ID',Editor.shadowRoot.querySelector('input').disabled,true);
  card.remove();return out;
 });
 const errors=[...page.errors];await page.close();
 for(const width of [280,390]){
  const preview=await openPage(browser,fixtureUrl.replace('/tests/fixture.html','/demo/attention.html'),{viewport:{width,height:800}});
  for(const dark of [false,true]){
   if(dark)await preview.locator('main>button').click();
   const size=await preview.locator('mousetrap-manager-card').evaluate(c=>({overflow:c.scrollWidth>c.clientWidth || document.documentElement.scrollWidth>innerWidth,height:c.getBoundingClientRect().height}));
   lines.push(!size.overflow?`ok   compact ${width}px ${dark?'dark':'light'} has no overflow`:`FAIL compact ${width}px overflow`);
   lines.push(size.height<300?`ok   compact ${width}px ${dark?'dark':'light'} fits two rows under 300px`:`FAIL compact ${width}px height ${size.height}`);
  }
  await preview.locator('main>select').selectOption('off');
  const height=await preview.locator('mousetrap-manager-card').evaluate(c=>c.getBoundingClientRect().height);
  lines.push(height===0?`ok   compact ${width}px normal mode takes no card height`:`FAIL normal compact height ${height}`);
  await preview.locator('main>select').selectOption('unavailable');
  const errorShown=await preview.locator('.attention-error').isVisible();
  lines.push(errorShown?`ok   compact ${width}px source outage stays visible`:`FAIL missing outage card`);
  errors.push(...preview.errors);await preview.close();
 }
 return {lines,errors};
}

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const contextMap = require('../../../web/context-map.js');
const source = fs.readFileSync(path.resolve(__dirname,'../../../web/context-pages.js'),'utf8');
const response = data => ({ok:true,status:200,json:async()=>data});
const element = () => ({isConnected:true,innerHTML:'',textContent:'',addEventListener(){},querySelector(){return null;}});

test('Knowledge does not automatically reopen an archived project when none are active',async()=>{
  const calls=[];
  const sandbox={window:{contextMap},fetch:async url=>{
    calls.push(url);
    return response(url.endsWith('/template')?{}:[{id:'retired',name:'Retired project',archived:true}]);
  }};
  vm.runInNewContext(source,sandbox);
  const root=element();await sandbox.window.contextPages.mount(root);
  assert.equal(calls.length,2);
  assert.match(root.innerHTML,/Select a project/);
  assert.match(root.innerHTML,/Create project/);
  assert.doesNotMatch(root.innerHTML,/cp-reader-body/);
});

test('late context response cannot populate a different persona or sign-in view', async () => {
  let release, count=0;
  const sandbox={window:{contextMap},fetch:async()=>{
    count++;
    if(count===1)return new Promise(resolve=>{release=resolve;});
    if(count===2)return response({});
    if(count===3)return response([{id:'public',name:'Public project'}]);
    if(count===5)return response([]);
    return response({project:{id:'public',name:'Public project'},contexts:[],relationships:[]});
  }};
  vm.runInNewContext(source,sandbox);
  const oldRoot=element(),newRoot=element();
  const pending=sandbox.window.contextPages.mount(oldRoot,async()=>{});
  oldRoot.isConnected=false;
  sandbox.window.contextPages.clear();
  await sandbox.window.contextPages.mount(newRoot,async()=>{});
  release(response({private:{pages:[]}}));
  await pending;
  assert.equal(oldRoot.innerHTML,'');
  assert.match(newRoot.innerHTML,/Public project/);
  assert.equal(count,5);
});

test('an expired context request returns control to the existing sign-in flow', async () => {
  let expired=0;
  const sandbox={window:{contextMap},fetch:async()=>({ok:false,status:401,json:async()=>({detail:'Sign in again'})})};
  vm.runInNewContext(source,sandbox);
  const root=element();
  await sandbox.window.contextPages.mount(root,async()=>{},()=>{expired++;sandbox.window.contextPages.clear();});
  assert.equal(expired,1);
  assert.equal(root.innerHTML,'');
  assert.equal(root.textContent,'');
});

const card = id => ({id,name:`Context ${id}`,title:`Context ${id}`,domain:'Requirements',revision:1,version:1,filename:`internal-${id}.md`,owner_type:'pm',status:'up_to_date',relationships:[],content:`Body ${id}`,owner:'pm',body:`Body ${id}`,dependencies:[]});
const link = (source_id,target_id,kind='depends_on') => ({source_id,target_id,kind});

function assertRoutesAvoidCards(map) {
  for(const edge of map.edges) {
    for(let index=1;index<edge.points.length;index++) {
      const [from,to]=[edge.points[index-1],edge.points[index]];
      // Adjacent-column Bezier curves stay inside their control-point corridor.
      for(let step=0;step<=20;step++) {
        const ratio=step/20,x=from[0]+(to[0]-from[0])*ratio,y=from[1]+(to[1]-from[1])*ratio;
        assert.ok(!map.nodes.some(node=>x>node.x+.1&&x<node.x+node.width-.1&&y>node.y+.1&&y<node.y+node.height-.1),`${edge.source_id} → ${edge.target_id} crosses a card`);
      }
    }
  }
}

test('dependency layers and long links keep connectors outside the cards', () => {
  const map=contextMap.layout(['A','B','C','D','E'].map(card),[link('B','A'),link('C','B'),link('C','A'),link('D','C'),link('E','D','references')]);
  assert.ok(map.nodes.find(node=>node.id==='A').x<map.nodes.find(node=>node.id==='B').x);
  assert.ok(map.nodes.find(node=>node.id==='B').x<map.nodes.find(node=>node.id==='C').x);
  assertRoutesAvoidCards(map);
  for(const node of map.nodes)assert.ok(node.x>=0&&node.y>=0&&node.x+node.width<=map.width&&node.y+node.height<=map.height);
});

test('cycles, self-links and missing relationship endpoints never break the map', () => {
  const map=contextMap.layout(['A','B','C'].map(card),[link('A','B'),link('B','A'),link('C','C'),link('A','missing'),link('B','A')]);
  assert.equal(map.nodes.length,3);
  assert.equal(map.edges.length,3);
  assert.ok(map.edges.every(edge=>!edge.path.includes('NaN')));
  assertRoutesAvoidCards(map);
});

test('map cards expose keyboard buttons and escape full user-supplied titles', () => {
  const title='A long context title with <script>alert("x")</script> & evidence';
  const html=contextMap.render([{...card('A'),title},card('B')],[link('B','A')],'A');
  assert.equal((html.match(/role="button"/g)||[]).length,2);
  assert.ok(!html.includes('role="img"'));
  assert.ok(!html.includes('<script>'));
  assert.match(html,/&lt;script&gt;/);
  assert.match(html,/aria-pressed="true"/);
  assert.match(html,/cp-node-consumer/);
});

test('rapid selection keeps the last selected page when an earlier request finishes late', async () => {
  let releaseB,releaseC;
  const handlers={},root={...element(),addEventListener:(name,handler)=>{handlers[name]=handler;}};
  const documents=['A','B','C'].map(card);
  const sandbox={window:{contextMap},fetch:async url=>{
    if(url.endsWith('/template'))return response({});
    if(url.endsWith('/projects?include_archived=true'))return response([{id:'current'}]);
    if(url.endsWith('/projects/current'))return response({project:{id:'current',name:'Test project'},contexts:documents,relationships:[]});
    if(url.endsWith('/proposals'))return response([]);
    if(url.endsWith('/sections'))return response({sections:[{key:'0',heading:'Content',body:'Body'}]});
    if(url.endsWith('/status'))return response({pending_proposals:0,status:'up_to_date'});
    if(url.endsWith('/versions'))return response([]);
    if(url.endsWith('/B'))return new Promise(resolve=>{releaseB=resolve;});
    if(url.endsWith('/C'))return new Promise(resolve=>{releaseC=resolve;});
    return response(card('A'));
  }};
  vm.runInNewContext(source,sandbox);
  await sandbox.window.contextPages.mount(root,async()=>{});
  const choose=id=>handlers.click({target:{closest:()=>({dataset:{cpAction:'select',id},focus(){}})}});
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  choose('B');await flush();
  choose('C');await flush();
  releaseC(response(card('C')));await flush();
  assert.match(root.innerHTML,/<h2[^>]*>Context C<\/h2>/);
  releaseB(response(card('B')));await flush();
  assert.match(root.innerHTML,/<h2[^>]*>Context C<\/h2>/);
  assert.doesNotMatch(root.innerHTML,/<h2[^>]*>Context B<\/h2>/);
});

function workspaceHarness() {
  const handlers={}, requests=[], documents=['A','B'].map(card);
  const root={...element(),addEventListener:(name,handler)=>{handlers[name]=handler;}};
  let pending;
  const sandbox={window:{contextMap},fetch:async url=>{
    requests.push(url);
    if(url.endsWith('/template'))return response({});
    if(url.endsWith('/projects?include_archived=true'))return response([{id:'current'}]);
    if(url.endsWith('/projects/current'))return response({project:{id:'current',name:'Test project'},contexts:documents,relationships:[link('B','A')]});
    if(url.endsWith('/proposals'))return response([]);
    if(url.endsWith('/sections'))return response({sections:[]});
    if(url.endsWith('/status'))return response({status:'up_to_date',pending_proposals:0});
    if(url.endsWith('/versions'))return response([]);
    if(pending)return new Promise(resolve=>{pending.release=resolve;});
    return response(card(url.endsWith('/B')?'B':'A'));
  }};
  vm.runInNewContext(source,sandbox);
  const click=(cpAction,extra={})=>handlers.click({target:{closest:()=>({dataset:{cpAction,...extra}})}});
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  return {root,requests,mount:()=>sandbox.window.contextPages.mount(root),click,flush,defer:()=>{pending={};return pending;}};
}

test('knowledge opens on the map and selection focuses content with supporting metadata',async()=>{
  const h=workspaceHarness();await h.mount();
  assert.match(h.root.innerHTML,/aria-label="Knowledge visualization"/);
  assert.match(h.root.innerHTML,/data-context-map/);
  assert.match(h.root.innerHTML,/aria-label="Open Context A, pm, version 1"/);
  assert.doesNotMatch(h.root.innerHTML,/internal-A\.md/);
  assert.doesNotMatch(h.root.innerHTML,/context-reader-title/);
  assert.ok(!h.requests.some(url=>url.includes('/contexts/')),'Opening a project must not load an arbitrary context');
  h.click('select',{id:'B'});await h.flush();
  assert.match(h.root.innerHTML,/id="context-reader-title"[^>]*>Context B/);
  assert.match(h.root.innerHTML,/Body B/);
  assert.match(h.root.innerHTML,/<aside[^>]*aria-label="Context metadata"/);
  assert.match(h.root.innerHTML,/Back to map/);
  assert.doesNotMatch(h.root.innerHTML,/data-context-map/);
  h.click('source');await h.flush();
  assert.match(h.root.innerHTML,/class="cp-markdown cp-source">Body B/);
  h.click('map');await h.flush();
  assert.match(h.root.innerHTML,/data-context-map/);
  assert.doesNotMatch(h.root.innerHTML,/context-reader-title/);
});

test('context editing separates the display name from the Markdown filename',async()=>{
  const h=workspaceHarness();await h.mount();
  h.click('select',{id:'A'});await h.flush();
  h.click('edit');await h.flush();
  assert.match(h.root.innerHTML,/Context name<input name="name" required[^>]*value="Context A"/);
  assert.match(h.root.innerHTML,/File name<input name="filename"[^>]*value="internal-A.md"/);
  h.click('cancel');await h.flush();
  assert.match(h.root.innerHTML,/id="context-reader-title"[^>]*>Context A/);
});

test('returning to the map cancels a pending context selection',async()=>{
  const h=workspaceHarness();await h.mount();
  h.click('select',{id:'A'});await h.flush();
  const pending=h.defer();
  h.click('select',{id:'B'});await h.flush();
  h.click('map');await h.flush();
  pending.release(response(card('B')));await h.flush();
  assert.match(h.root.innerHTML,/aria-label="Knowledge visualization"/);
  assert.match(h.root.innerHTML,/data-context-map/);
  assert.doesNotMatch(h.root.innerHTML,/context-reader-title/);
});


function mapHarness(initialView) {
  const handlers=new Map(), captured=new Set(), output={textContent:''}, zoomIn={}, zoomOut={}, attributes={};
  const scene={setAttribute:(key,value)=>{attributes[key]=value;}};
  const svg={dataset:{mapWidth:'1600',mapHeight:'600'},querySelector:()=>scene};
  const classes=new Set();
  const viewport={
    clientWidth:800,clientHeight:400,clientLeft:0,clientTop:0,
    querySelector:()=>svg,focus(){},
    getBoundingClientRect:()=>({left:20,top:30,right:820,bottom:430}),
    classList:{add:name=>classes.add(name),remove:name=>classes.delete(name)},
    setPointerCapture:id=>captured.add(id),hasPointerCapture:id=>captured.has(id),releasePointerCapture:id=>captured.delete(id),
    addEventListener:(type,handler)=>{if(!handlers.has(type))handlers.set(type,[]);handlers.get(type).push(handler);},
    removeEventListener:(type,handler)=>handlers.set(type,handlers.get(type).filter(item=>item!==handler)),
  };
  const root={querySelector:selector=>({
    '.cp-map-viewport':viewport,'[data-cp-zoom]':output,
    '[data-cp-action="map-zoom-in"]':zoomIn,'[data-cp-action="map-zoom-out"]':zoomOut,
  })[selector]};
  const snapshots=[];
  const controller=contextMap.mount(root,initialView,view=>snapshots.push(view));
  const emit=(type,values={})=>{
    const event={button:0,pointerId:1,pointerType:'mouse',clientX:120,clientY:130,deltaX:0,deltaY:0,deltaMode:0,detail:1,
      target:{closest:()=>null},preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...values};
    for(const handler of handlers.get(type)||[])handler(event);
    return event;
  };
  return {controller,emit,viewport,output,zoomIn,zoomOut,attributes,captured,handlers,snapshots};
}
const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-8,actual+' != '+expected);

test('fitted maps can pan freely and dragging a card does not open it',()=>{
  const h=mapHarness(), before=h.controller.getView();
  assert.ok(before.x>=0&&before.y>=0);
  assert.ok(before.x+1600*before.zoom<=800&&before.y+600*before.zoom<=400);
  h.emit('pointerdown');
  h.emit('pointermove',{clientX:255,clientY:175});
  const after=h.controller.getView();
  near(after.x,before.x+135);near(after.y,before.y+45);
  assert.equal(after.fitted,false);
  assert.ok(h.attributes.transform.includes('translate('));
  h.emit('pointerup');
  const dragClick=h.emit('click');
  assert.ok(dragClick.prevented&&dragClick.stopped);
  assert.equal(h.captured.size,0);
  h.emit('pointerdown');h.emit('pointerup');
  assert.ok(!h.emit('click').prevented,'A stationary tap/click must still select a card');
  h.controller.destroy();
});

test('wheel zoom keeps the world point under the cursor and Shift-wheel pans',()=>{
  const h=mapHarness(), before=h.controller.getView(), cursor={x:300,y:180};
  const world={x:(cursor.x-before.x)/before.zoom,y:(cursor.y-before.y)/before.zoom};
  const event=h.emit('wheel',{clientX:320,clientY:210,deltaY:-160});
  const after=h.controller.getView();
  assert.ok(event.prevented&&after.zoom>before.zoom);
  near((cursor.x-after.x)/after.zoom,world.x);near((cursor.y-after.y)/after.zoom,world.y);
  h.emit('wheel',{deltaY:50,shiftKey:true});
  const panned=h.controller.getView();
  near(panned.x,after.x-50);near(panned.zoom,after.zoom);
  h.controller.destroy();
});

test('touch pinch uses both fingers and transitions smoothly back to one-finger panning',()=>{
  const h=mapHarness({x:0,y:0,zoom:1,fitted:false});
  h.emit('pointerdown',{pointerType:'touch',pointerId:1,clientX:120,clientY:130});
  h.emit('pointerdown',{pointerType:'touch',pointerId:2,clientX:220,clientY:130});
  h.emit('pointermove',{pointerType:'touch',pointerId:2,clientX:320,clientY:130});
  let view=h.controller.getView();
  near(view.zoom,2);near(view.x,-100);near(view.y,-100);
  h.emit('pointermove',{pointerType:'touch',pointerId:1,clientX:170,clientY:130});
  h.emit('pointermove',{pointerType:'touch',pointerId:2,clientX:370,clientY:130});
  view=h.controller.getView();
  near(view.zoom,2);near(view.x,-50);
  h.emit('pointerup',{pointerType:'touch',pointerId:2});
  h.emit('pointermove',{pointerType:'touch',pointerId:1,clientX:190,clientY:130});
  near(h.controller.getView().x,-30);near(h.controller.getView().zoom,2);
  h.emit('pointercancel',{pointerId:1});
  assert.equal(h.captured.size,0);
  h.controller.destroy();
});

test('zoom is bounded and keyboard Fit/Reset recover a lost camera',()=>{
  const h=mapHarness();
  for(let i=0;i<50;i++)h.controller.command('map-zoom-in');
  assert.equal(h.controller.getView().zoom,4);assert.equal(h.zoomIn.disabled,true);
  for(let i=0;i<60;i++)h.controller.command('map-zoom-out');
  assert.equal(h.controller.getView().zoom,.02);assert.equal(h.zoomOut.disabled,true);
  h.emit('keydown',{key:'0'});
  near(h.controller.getView().zoom,1);near(h.controller.getView().x,-400);
  h.emit('keydown',{key:'ArrowRight',target:h.viewport});
  near(h.controller.getView().x,-440);
  h.emit('keydown',{key:'f'});
  assert.equal(h.controller.getView().fitted,true);
  assert.ok(h.controller.getView().x>=0);
  h.controller.destroy();
});

test('camera state survives replacement and old gesture handlers/captures are removed',()=>{
  const first=mapHarness();
  first.emit('pointerdown');first.emit('pointermove',{clientX:620,clientY:380});
  const saved=first.controller.getView();
  first.controller.destroy();
  assert.equal(first.captured.size,0);
  assert.ok([...first.handlers.values()].every(handlers=>handlers.length===0));
  const next=mapHarness(saved);
  assert.deepEqual(next.controller.getView(),saved);
  const snapshotCount=first.snapshots.length;
  first.emit('wheel',{deltaY:100});
  assert.equal(first.snapshots.length,snapshotCount,'Detached map handlers cannot update the next view');
  next.controller.destroy();
});


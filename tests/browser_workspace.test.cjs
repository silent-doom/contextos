const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('web/app.js','utf8');

// Run the shipped controller with DOM sinks and API fixtures, without a browser.
function workspace(fixture) {
  const elements = new Map(), handlers = {document:{},window:{}}, storage = new Map(), calls = [];
  let hash='';
  const location={get hash(){return hash;},set hash(value){hash=value && !value.startsWith('#') ? `#${value}` : value;}};
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      innerHTML:'',textContent:'',value:'',open:false,classList:{add(){},remove(){},toggle(){}},
      addEventListener(){},replaceChildren(){this.innerHTML='';},close(){this.open=false;},
      showModal(){this.open=true;},focus(){},scrollIntoView(){}
    });
    return elements.get(selector);
  }
  const context = vm.createContext({
    document:{querySelector:element,addEventListener:(name,fn)=>handlers.document[name]=fn,
      body:element('body'),getElementById:id=>element(`#${id}`)},
    window:{addEventListener:(name,fn)=>handlers.window[name]=fn,scrollTo(){},
      contextosIdentity:{configuration:()=>new Promise(()=>{})}},
    location,sessionStorage:{getItem:key=>storage.get(key)??null,
      setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)},
    requestAnimationFrame:fn=>fn(),setTimeout:()=>1,clearTimeout(){},
    fetch:async (url,options)=>{
      calls.push({url,options});
      const body = url==='/api/workspace' ? context.fixture : {recorded:true};
      return {ok:true,json:async()=>body};
    },fixture
  });
  vm.runInContext(source,context);
  return {element,handlers,storage,calls,context,
    run:code=>vm.runInContext(code,context),
    render:(route='',runId=null)=>{
      context.route=route;context.runId=runId;
      vm.runInContext('state=fixture;currentView=resolveView(route);activeRun=state.tasks.find(t=>t.id===runId);render();',context);
    }};
}

function state() {
  return {actor:'architect-me',role:'architect',auth_mode:'firebase',ai_mode:'offline',
    project:{name:'Test project'},contexts:[],proposals:[],tasks:[],events:[],usage:[],
    next_actions:[{kind:'task',query:'Review the accepted design'}]};
}
function run(id,actor,query) {
  return {id,actor,role:'architect',query,stale:true,output:'Existing answer',created_at:'2026-10-18T12:00:00Z',
    manifest:{sources:[],budget:6000,estimated_tokens:1,estimator:'test'},usage:{model:null,total_tokens:0}};
}

test('Overview is the landing page and four primary destinations preserve task/review bookmarks',()=>{
  const fixture=state();fixture.auth_mode='demo';
  const page=workspace(fixture);
  for (const route of ['', 'overview', 'constructor', 'unknown']) {
    page.render(route);
    assert.equal(page.element('#crumb').textContent,'Overview');
    assert.match(page.element('#main').innerHTML,/Needs your attention/);
    assert.doesNotMatch(page.element('#main').innerHTML,/id="task-form"/);
    assert.deepEqual([...page.element('#nav').innerHTML.matchAll(/href="#([^"]+)"/g)].map(m=>m[1]),['overview','work','knowledge','inbox']);
    assert.match(page.element('#nav').innerHTML,/href="#overview" class="nav-item active" aria-current="page"/);
  }
  for (const route of ['tasks', 'work']) {
    page.render(route);
    assert.equal(page.element('#crumb').textContent,'Work');
    assert.equal((page.element('#main').innerHTML.match(/id="task-form"/g)||[]).length,1);
  }
  page.render('reviews');assert.equal(page.element('#crumb').textContent,'Inbox');
  assert.match(page.element('#secondary-nav').innerHTML,/href="#demo"/);
  assert.match(page.element('#mobile-tools').innerHTML,/href="#insights"/);
  fixture.auth_mode='firebase';page.render('work');
  assert.doesNotMatch(page.element('#secondary-nav').innerHTML,/href="#demo"/);
});

test('Overview prioritizes changed required context and keeps personal actions scoped',async()=>{
  const fixture=state();
  fixture.project.name='Checkout <project>';
  fixture.contexts=[{id:'REQ-1',title:'Required contract',revision:2,mandatory:true,status:'accepted'},
    {id:'ARC-1',title:'Design',revision:2,mandatory:false,status:'accepted'}];
  const required=run('critical-run',fixture.actor,'Check <required> work');
  required.manifest.sources=[{id:'REQ-1',title:'Required contract',revision:1,body:'Original requirement'}];
  fixture.tasks=[run('normal',fixture.actor,'Ordinary stale work'),
    run('someone-else','other-architect','Other user task'),required];
  fixture.proposals=[
    {id:'reviewable',title:'Review <design>',domain:'Architecture',author:'developer',status:'pending'},
    {id:'self',title:'My own pending proposal',domain:'Architecture',author:fixture.actor,status:'pending'},
    {id:'other',title:'Another domain proposal',domain:'Requirements',author:'product',status:'pending'}];
  fixture.events=[{action:'Revision published',detail:'Required <contract> updated',actor:'product',outcome:'completed',at:'2026-10-18T12:00:00Z'}];
  const page=workspace(fixture);page.render('overview');
  const html=page.element('#main').innerHTML;
  assert.match(html,/Checkout &lt;project&gt;/);
  assert.match(html,/1 critical item/);
  assert.match(html,/REQ-1 v1 → v2/);
  assert.match(html,/Review &lt;design&gt;/);
  assert.match(html,/Required &lt;contract&gt; updated/);
  assert.doesNotMatch(html,/My own pending proposal|Other user task|Another domain proposal|data-action="approve"/);
  assert.ok(html.indexOf('Check &lt;required&gt; work')<html.indexOf('Review &lt;design&gt;'));
  assert.ok(html.indexOf('Review &lt;design&gt;')<html.indexOf('Ordinary stale work'));
  assert.match(html,/Accepted topics[\s\S]*?stat-value">2</);
  assert.match(html,/Pending proposals[\s\S]*?stat-value">3</);
  assert.match(html,/Affected runs[\s\S]*?stat-value">3</);
  assert.match(html,/Required constraints[\s\S]*?stat-value">1</);
  await page.run('action({dataset:{action:"open-run",id:"critical-run"}})');
  await page.handlers.window.hashchange();
  assert.match(page.element('#main').innerHTML,/REQ-1 · v1/);
  assert.equal(page.element('#crumb').textContent,'Work');
});

test('Overview does not invent critical issues, project health or unresolved historical failures',()=>{
  const fixture=state(), page=workspace(fixture);
  page.render('overview');
  assert.match(page.element('#main').innerHTML,/No shared knowledge yet/);
  assert.match(page.element('#main').innerHTML,/data-action="ingest"/);
  assert.doesNotMatch(page.element('#main').innerHTML,/class="tag critical"|project is healthy/i);
  fixture.contexts=[{id:'REQ-1',revision:1,status:'accepted',mandatory:true}];
  const stale=run('stale',fixture.actor,'A dependency changed');
  stale.manifest.sources=[{id:'REQ-1',revision:1}];
  fixture.tasks=[stale];
  fixture.usage=[{status:'failed'},{status:'completed'}];
  page.render('overview');
  assert.match(page.element('#main').innerHTML,/Needs review/);
  assert.doesNotMatch(page.element('#main').innerHTML,/class="tag critical"|Latest model attempt failed/);
  fixture.usage.push({status:'failed'});page.render('overview');
  assert.match(page.element('#main').innerHTML,/Latest model attempt failed/);
  assert.match(page.element('#main').innerHTML,/View activity/);
});

test('Overview detects proposal base conflicts without offering publication',async()=>{
  const fixture=state();
  fixture.contexts=[{id:'ARC-1',status:'accepted',revision:2}];
  fixture.proposals=[{id:'stale-proposal',context_id:'ARC-1',base_revision:1,title:'Old proposal',domain:'Architecture',author:'developer',status:'pending'}];
  const page=workspace(fixture);page.render('overview');
  assert.match(page.element('#main').innerHTML,/Conflict/);
  assert.match(page.element('#main').innerHTML,/Based on v1; accepted context is now v2/);
  assert.doesNotMatch(page.element('#main').innerHTML,/data-action="approve"/);
  page.run('inboxFilter="history"');
  await page.run('action({dataset:{action:"navigate",view:"inbox",filter:"mine"}})');
  await page.handlers.window.hashchange();
  assert.equal(page.run('inboxFilter'),'mine');
  assert.match(page.element('#main').innerHTML,/Old proposal/);
  fixture.proposals[0].author=fixture.actor;page.render('overview');
  assert.match(page.element('#main').innerHTML,/Conflict/);
  assert.match(page.element('#main').innerHTML,/data-view="inbox" data-filter="pending"/);
  fixture.proposals[0].status='published';page.render('overview');
  assert.doesNotMatch(page.element('#main').innerHTML,/Old proposal/);
});

test('Overview refreshes on entry and on request using the current permitted snapshot',async()=>{
  const fixture=state(),page=workspace(fixture);page.render('work');
  page.context.fixture={...fixture,project:{name:'Updated project'}};
  page.context.location.hash='#overview';await page.handlers.window.hashchange();
  assert.match(page.element('#main').innerHTML,/Updated project/);
  page.context.fixture={...fixture,project:{name:'Refreshed again'}};
  await page.run('action({dataset:{action:"refresh-overview"}})');
  assert.match(page.element('#main').innerHTML,/Refreshed again/);
  assert.equal(page.calls.filter(c=>c.url==='/api/workspace').length,2);
});

test('Inbox counts owned reviews and affected personal runs without granting self-review',async()=>{
  const fixture=state();
  fixture.proposals=[
    {id:'reviewable',title:'Reviewable design',domain:'Architecture',author:'developer',status:'pending'},
    {id:'self',title:'My own proposal',domain:'Architecture',author:fixture.actor,status:'pending'},
    {id:'other-domain',title:'Product proposal',domain:'Requirements',author:'product',status:'pending'},
  ];
  fixture.tasks=[run('mine',fixture.actor,'My affected task'),run('someone-else','other-architect','Other user task')];
  const page=workspace(fixture);page.render('inbox');
  assert.match(page.element('#nav').innerHTML,/2 items need your attention/);
  assert.match(page.element('#main').innerHTML,/My affected task/);
  assert.doesNotMatch(page.element('#main').innerHTML,/Other user task/);
  assert.match(page.element('#main').innerHTML,/data-action="approve" data-id="reviewable"/);
  assert.doesNotMatch(page.element('#main').innerHTML,/data-action="approve" data-id="self"/);
  await page.run('action({dataset:{action:"inbox-filter",filter:"mine"}})');
  assert.match(page.element('#main').innerHTML,/id="proposal-reviewable"/);
  assert.doesNotMatch(page.element('#main').innerHTML,/id="proposal-(self|other-domain)"/);
});

test('opening an old run keeps its original source inspector after accepted content changes',async()=>{
  const fixture=state(), old=run('old',fixture.actor,'Earlier work');
  fixture.contexts=[{id:'ARC-1',body:'New accepted body',revision:2}];
  old.manifest.sources=[{id:'ARC-1',title:'Original <design>',body:'Original source body',revision:1}];
  fixture.tasks=[old];
  const page=workspace(fixture);page.render('inbox');
  await page.run('action({dataset:{action:"open-run",id:"old"}})');
  assert.equal(page.context.location.hash,'#work');
  await page.handlers.window.hashchange();
  assert.match(page.element('#main').innerHTML,/Original &lt;design&gt;/);
  assert.match(page.element('#main').innerHTML,/ARC-1 · v1/);
  await page.run('action({dataset:{action:"manifest",id:"old"}})');
  assert.match(page.element('#dialog-content').innerHTML,/Original source body/);
  assert.doesNotMatch(page.element('#dialog-content').innerHTML,/New accepted body/);
  assert.equal(JSON.parse(page.calls.at(-1).options.body).target_id,'old');
});

test('task drafts and advanced budgets survive navigation and clear on sign-out',async()=>{
  const page=workspace(state());page.render('work');
  page.handlers.document.input({target:{id:'task-query',value:'Draft <work>'}});
  page.handlers.document.change({target:{id:'task-budget',value:'3000'}});
  page.context.location.hash='#knowledge';await page.handlers.window.hashchange();
  page.context.location.hash='#work';await page.handlers.window.hashchange();
  assert.match(page.element('#main').innerHTML,/Draft &lt;work&gt;/);
  assert.match(page.element('#main').innerHTML,/value="3000" selected/);
  page.run('clearProtectedView()');
  assert.equal(page.storage.size,0);
  for (const selector of ['#main','#nav','#secondary-nav','#mobile-tools']) assert.equal(page.element(selector).innerHTML,'');
});

test('entering Inbox refreshes shared changes and history never offers publication',async()=>{
  const fixture=state(),page=workspace(fixture);page.render('work');
  page.context.fixture={...fixture,proposals:[{id:'new',title:'A newly shared decision',domain:'Architecture',
    author:'developer',status:'published',reviewer:'architect-me'}]};
  page.context.location.hash='#reviews';await page.handlers.window.hashchange();
  assert.equal(page.calls.filter(c=>c.url==='/api/workspace').length,1);
  await page.run('action({dataset:{action:"inbox-filter",filter:"history"}})');
  assert.match(page.element('#main').innerHTML,/A newly shared decision/);
  assert.doesNotMatch(page.element('#main').innerHTML,/data-action="approve"/);
});

test('Knowledge search combines text and domain filters without replacing the search input',()=>{
  const fixture=state();
  fixture.contexts=[
    {id:'ARC-1',title:'Retry design',body:'Use idempotency',domain:'Architecture',owner:'architect',revision:1},
    {id:'REQ-1',title:'Payment requirement',body:'Retry transient failures',domain:'Requirements',owner:'pm',revision:1},
  ];
  const page=workspace(fixture);page.render('knowledge');
  const search=page.element('#search');
  page.handlers.document.input({target:{id:'search',value:'RETRY'}});
  assert.match(page.element('#knowledge-results').innerHTML,/Retry design/);
  assert.match(page.element('#knowledge-results').innerHTML,/Payment requirement/);
  page.handlers.document.change({target:{id:'domain-filter',value:'Architecture'}});
  assert.match(page.element('#knowledge-results').innerHTML,/Retry design/);
  assert.doesNotMatch(page.element('#knowledge-results').innerHTML,/Payment requirement/);
  assert.equal(page.element('#search'),search);
});

for (const route of ['inbox','overview']) test(`a late ${route} response cannot restore protected content after sign-out`,async()=>{
  const page=workspace(state());page.render('work');
  let deliver;
  page.context.fixture=new Promise(resolve=>deliver=resolve);
  page.context.location.hash=`#${route}`;
  const navigation=page.handlers.window.hashchange();
  page.run('clearProtectedView()');
  deliver({...state(),project:{name:'Protected project'}});
  await navigation;
  assert.equal(page.run('state'),undefined);
  assert.equal(page.element('#main').innerHTML,'');
  assert.equal(page.element('#nav').innerHTML,'');
});

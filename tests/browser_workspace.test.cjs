const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('web/app.js','utf8');

// Run the shipped controller with DOM sinks and API fixtures, without a browser.
function workspace(fixture, {url='http://testserver/', contextResponses={}}={}) {
  const elements = new Map(), handlers = {document:{},window:{}}, storage = new Map(), calls = [];
  let currentUrl=new URL(url);
  const location={get hash(){return currentUrl.hash;},set hash(value){currentUrl.hash=value;},
    get pathname(){return currentUrl.pathname;},get search(){return currentUrl.search;}};
  const history={state:null,replaceState(state,title,url){this.state=state;currentUrl=new URL(url,currentUrl);}};
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      innerHTML:'',textContent:'',value:'',open:false,classList:{add(){},remove(){},toggle(){}},
      isConnected:true,querySelector(){return null;},querySelectorAll(){return [];},
      addEventListener(){},replaceChildren(){this.innerHTML='';},close(){this.open=false;},
      showModal(){this.open=true;},focus(){},scrollIntoView(){}
    });
    return elements.get(selector);
  }
  const context = vm.createContext({
    crypto:require('node:crypto').webcrypto,
    document:{querySelector:element,addEventListener:(name,fn)=>handlers.document[name]=fn,
      body:element('body'),getElementById:id=>element(`#${id}`)},
    window:{addEventListener:(name,fn)=>handlers.window[name]=fn,scrollTo(){},
      contextosIdentity:{configuration:()=>new Promise(()=>{})}},
    location,history,sessionStorage:{getItem:key=>storage.get(key)??null,
      setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)},
    requestAnimationFrame:fn=>fn(),setTimeout:()=>1,clearTimeout(){},
    fetch:async (url,options)=>{
      calls.push({url,options});
      const body = url==='/api/workspace' ? context.fixture : Object.hasOwn(contextResponses,url) ? contextResponses[url]
        : url==='/api/context/projects?include_archived=true' ? [] : {recorded:true};
      return {ok:true,json:async()=>body};
    },fixture
  });
  // Load the shipped modules in the same order as index.html, including cleanup.
  vm.runInContext(fs.readFileSync('web/context-map.js','utf8'),context);
  vm.runInContext(fs.readFileSync('web/context-pages.js','utf8'),context);
  vm.runInContext(fs.readFileSync('web/conversations.js','utf8'),context);
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
    assert.deepEqual([...page.element('#nav').innerHTML.matchAll(/href="([^"]+)"/g)].map(m=>m[1]),['#overview','#work','/knowledge','#inbox']);
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

test('direct Knowledge URLs mount the real context-pages module and preserve the query',async()=>{
  const fixture={...state(),context_pages_enabled:true};
  const page=workspace(fixture,{url:'http://testserver/knowledge?project=checkout'});
  assert.equal(page.run('currentView'),'knowledge');
  page.render('knowledge');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(page.context.location.pathname,'/knowledge');
  assert.equal(page.context.location.search,'?project=checkout');
  assert.equal(page.context.location.hash,'');
  assert.match(page.element('#main').innerHTML,/id="context-pages"/);
  assert.match(page.element('#context-pages').innerHTML,/Create your first project/);
  assert.match(page.element('#nav').innerHTML,/href="\/knowledge" class="nav-item active"/);
  assert.deepEqual(page.calls.map(call=>call.url),['/api/context/template','/api/context/projects?include_archived=true']);
});

test('legacy Knowledge/task routes and popstate retain canonical paths and Inbox filters',async()=>{
  const page=workspace(state(),{url:'http://testserver/knowledge?project=checkout#tasks'});
  page.render('tasks');
  assert.equal(page.context.location.pathname,'/');
  assert.equal(page.context.location.hash,'#work');
  assert.equal(page.context.location.search,'?project=checkout');
  assert.match(page.element('#main').innerHTML,/id="task-form"/);
  page.context.location.hash='#contextpages';await page.handlers.window.hashchange();
  assert.equal(page.context.location.pathname,'/knowledge');
  assert.equal(page.context.location.hash,'');
  assert.equal(page.element('#crumb').textContent,'Knowledge');
  page.context.history.replaceState(null,'','/?project=checkout#reviews');
  await page.handlers.window.popstate();
  assert.equal(page.element('#crumb').textContent,'Inbox');
  assert.equal(page.run('inboxFilter'),'pending');
  assert.match(page.element('#mobile-tools').innerHTML,/href="#insights"/);
});

test('a plain Knowledge link click uses the app router and closes mobile tools',async()=>{
  const page=workspace(state());page.render('overview');
  page.element('#workspace-tools').open=true;
  let prevented=false;
  await page.handlers.document.click({button:0,preventDefault(){prevented=true;},
    target:{closest:selector=>selector==='a[href="/knowledge"]' ? {} : null}});
  await page.handlers.window.hashchange();
  assert.equal(prevented,true);
  assert.equal(page.context.location.pathname,'/knowledge');
  assert.equal(page.element('#workspace-tools').open,false);
  assert.equal(page.element('#crumb').textContent,'Knowledge');
});

for (const exit of ['navigation','sign-out']) test(`pending shared-knowledge requests are discarded after ${exit}`,async()=>{
  let deliver;
  const pending=new Promise(resolve=>deliver=resolve);
  const page=workspace({...state(),context_pages_enabled:true},{contextResponses:{'/api/context/template':pending}});
  page.render('knowledge');
  const root=page.element('#context-pages'),original=root.innerHTML;
  if (exit==='navigation') {
    await page.run('action({dataset:{action:"navigate",view:"work"}})');
    await page.handlers.window.hashchange();
  } else page.run('clearProtectedView()');
  deliver({content:'Protected context that arrived too late'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(root.innerHTML,original);
  assert.equal(page.calls.filter(call=>call.url.startsWith('/api/context/')).length,1);
  if (exit==='navigation') assert.match(page.element('#main').innerHTML,/id="task-form"/);
  else {
    assert.equal(page.run('state'),undefined);
    assert.equal(page.element('#main').innerHTML,'');
  }
});

test('a context-pages 401 clears the workspace and opens the existing sign-in flow',async()=>{
  const page=workspace({...state(),context_pages_enabled:true});
  page.run('identityConfig={auth_mode:"firebase",login_ready:true}');
  page.context.fetch=async()=>({ok:false,status:401,json:async()=>({detail:'Sign in again'})});
  page.render('knowledge');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(page.run('state'),undefined);
  assert.equal(page.element('#nav').innerHTML,'');
  assert.match(page.element('#main').innerHTML,/Sign in again/);
  assert.match(page.element('#main').innerHTML,/id="login-form"/);
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

test('project selection scopes Work, Inbox review and exports to the same accepted pages',async()=>{
  const fixture=state();
  const project={...state(),selected_project_id:'PRJ-1',project:{id:'PRJ-1',name:'Shared checkout'},projects:[{id:'PRJ-1',name:'Shared checkout'}]};
  project.proposals=[{id:'PROP-1',context_id:'CTX-1',project_id:'PRJ-1',title:'Retry limit',domain:'Architecture',review_role:'architect',author:'developer',status:'pending',hash:'abc',body:'Two attempts'}];
  const page=workspace(fixture,{contextResponses:{'/api/workspace?project_id=PRJ-1':project}});
  page.render('work');await page.run('selectProject("PRJ-1")');
  assert.equal(page.storage.get('context-project'),'PRJ-1');
  assert.equal(page.element('#project-name').textContent,'Shared checkout');
  assert.equal(page.run('selectedProject'),'PRJ-1');
  await page.run('action({dataset:{action:"approve",id:"PROP-1"}})');
  const review=page.calls.find(c=>c.url==='/api/context/projects/PRJ-1/proposals/PROP-1/review');
  assert.equal(JSON.parse(review.options.body).decision,'approve');
  page.run('clearProtectedView()');
  assert.equal(page.storage.has('context-project'),false);
});

test('new required constraints are critical even when the earlier run never loaded them',()=>{
  const fixture=state();
  const prior=run('RUN-1',fixture.actor,'Prior work');
  prior.context_changes=[{context_id:'SEC-2',title:'New logging rule',revision:1,mandatory:true,reason:'Provider policy changed'}];
  fixture.tasks=[prior];const page=workspace(fixture);page.render('overview');
  assert.match(page.element('#main').innerHTML,/1 critical item/);
  assert.match(page.element('#main').innerHTML,/New logging rule v1/);
  page.render('work','RUN-1');
  assert.match(page.element('#main').innerHTML,/Provider policy changed/);
});

test('Work reopens private conversations and inspects the selected turn original sources',async()=>{
  const fixture=state(),first=run('RUN-1',fixture.actor,'Implement retries');
  first.stale=false;first.status='succeeded';first.conversation_id='CHAT-1';
  first.manifest.sources=[{id:'CTX-1',revision:1,title:'Retry design',body:'Three attempts'}];
  fixture.tasks=[first];fixture.conversations=[{id:'CHAT-1',title:'Payment retries',turn_ids:['RUN-1'],updated_at:first.created_at}];
  const chat={...fixture.conversations[0],turns:[first]};
  const page=workspace(fixture,{contextResponses:{'/api/conversations/CHAT-1':chat}});
  page.render('work');await page.run('action({dataset:{action:"open-conversation",id:"CHAT-1"}})');
  assert.match(page.element('#main').innerHTML,/Private task conversation/);
  assert.match(page.element('#main').innerHTML,/Follow-up/);
  assert.match(page.element('#main').innerHTML,/CTX-1 · v1/);
  page.run('clearProtectedView()');
  assert.equal(page.run('chats.current'),null);
});

test('initial load uses the existing Knowledge project for every workspace view',async()=>{
  const initial={...state(),projects:[{id:'PRJ-1',name:'Team project'}]};
  const selected={...state(),project:{id:'PRJ-1',name:'Team project'},projects:initial.projects,
    selected_project_id:'PRJ-1',contexts:[]};
  const page=workspace(initial,{contextResponses:{'/api/workspace?project_id=PRJ-1':selected}});
  await page.run('refresh()');
  assert.equal(page.run('selectedProject'),'PRJ-1');
  assert.equal(page.run('state.project.id'),'PRJ-1');
  assert.equal(page.element('#project-name').textContent,'Team project');
  assert.match(page.element('#main').innerHTML,/Team project/);
  assert.equal(page.calls.filter(c=>c.url==='/api/workspace?project_id=PRJ-1').length,1);
});

test('an unavailable saved project falls back to permitted project knowledge',async()=>{
  const initial={...state(),projects:[{id:'PRJ-2',name:'Available project'}]};
  const available={...state(),project:{id:'PRJ-2',name:'Available project'},projects:initial.projects};
  const page=workspace(initial);page.render('overview');
  page.run('selectedProject="removed-project"');
  page.context.fetch=async url=>({ok:!url.includes('removed-project'),status:url.includes('removed-project')?404:200,
    json:async()=>url.includes('removed-project')?{detail:'Project unavailable'}:url.includes('PRJ-2')?available:initial});
  await page.run('refresh()');
  assert.equal(page.run('selectedProject'),'PRJ-2');
  assert.equal(page.element('#project-name').textContent,'Available project');
});

test('a retired selected project does not reopen sample content on Overview',async()=>{
  const initial={...state(),projects:[{id:'PRJ-2',name:'Active project'}]};
  const retired={...state(),project:{id:'PRJ-old',name:'Retired project',archived:true},projects:initial.projects};
  const active={...state(),project:{id:'PRJ-2',name:'Active project'},projects:initial.projects};
  const page=workspace(initial,{contextResponses:{'/api/workspace?project_id=PRJ-old':retired,'/api/workspace?project_id=PRJ-2':active}});
  page.render('overview');page.run('selectedProject="PRJ-old"');await page.run('refresh()');
  assert.equal(page.run('selectedProject'),'PRJ-2');
  assert.match(page.element('#main').innerHTML,/Active project/);
  assert.doesNotMatch(page.element('#main').innerHTML,/Retired project/);
});

test('More closes when its current link is selected, on outside click and on Escape',async()=>{
  const page=workspace(state());page.render('insights');
  const menu=page.element('#workspace-tools');
  menu.open=true;
  await page.handlers.document.click({target:{closest:selector=>['#workspace-tools','#mobile-tools a'].includes(selector)?{}:null}});
  assert.equal(menu.open,false);
  menu.open=true;
  await page.handlers.document.click({target:{closest:()=>null}});
  assert.equal(menu.open,false);
  let focused=false;page.element('#workspace-tools summary').focus=()=>focused=true;
  menu.open=true;page.handlers.document.keydown({key:'Escape'});
  assert.equal(menu.open,false);assert.equal(focused,true);
});

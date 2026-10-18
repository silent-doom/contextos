'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {
 demo:'M8 5l11 7-11 7z',
 overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
 knowledge:'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6',
 tasks:'M4 5h16v12H9l-5 4z M8 9h8 M8 13h5',
 reviews:'M9 4H5v17h14V4h-4 M9 2h6v4H9z M8 12l3 3 5-6',
 insights:'M4 20V4 M4 20h17 M8 15l4-5 4 3 5-8',
 arrow:'M4 12h16 M15 7l5 5-5 5',
 shield:'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6',
 branch:'M6 3v18 M6 16c0-8 12-1 12-10 M3 3h6 M15 3h6 M3 21h6',
 spark:'M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',
 clock:'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
 plus:'M12 5v14 M5 12h14',
 check:'M5 12l4 4L19 6'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.knowledge}"/></svg>`;
const roleNames = {developer:'Developer',pm:'Product manager',architect:'Architect',qa:'QA engineer',security:'Security'};
const owners = {Requirements:'pm',Architecture:'architect',Implementation:'developer',Quality:'qa',Security:'security'};
const navItems = [['overview','Overview','overview'],['work','Work','tasks'],['knowledge','Knowledge','knowledge'],['inbox','Inbox','reviews']];
const secondaryItems = [['insights','Activity & usage','insights'],['demo','Walkthroughs','demo']];
const routeAliases = {tasks:'work',reviews:'inbox',contextpages:'knowledge'};
function resolveView(view) {
  return Object.hasOwn(routeAliases,view) ? routeAliases[view] : ([...navItems,...secondaryItems].some(([id]) => id === view) ? view : 'overview');
}
function viewLabel(view) {
  return [...navItems,...secondaryItems].find(([id]) => id === resolveView(view))[1];
}
let state, activeRun, selectedContext, toastTimer, queryFilter = '', domainFilter = 'All domains';
let currentView = viewFromUrl(), inboxFilter = 'pending';
let busy = false;
let demoPositions = {}, demoCompleted = {};
let demoCatalog = [], demoRole = 'all', demoCategory = 'All cases', demoSelected = 'handoff', demoReports = {}, demoRunning = null;
let identityConfig, protectedVersion = 0;

async function api(path, body) {
  const response = await fetch(`/api/${path}`, {method:body === undefined ? 'GET' : 'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-ContextOS-Client':'workspace'}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(x => `${x.loc.at(-1)}: ${x.msg}`).join('; ') : data.detail;
    const error = new Error(detail || 'The request could not be completed.');
    error.status = response.status;
    if (response.status === 401 && identityConfig?.auth_mode === 'firebase') showSignIn(error.message);
    throw error;
  }
  return data;
}
function toast(message, error = false) {
  clearTimeout(toastTimer); const el = $('#toast'); el.textContent = message;
  el.className = `visible${error ? ' error' : ''}`; toastTimer = setTimeout(() => el.className = '', 6500);
}
async function refresh() {
  const version = protectedVersion;
  const next = await api('workspace');
  if (version !== protectedVersion) return;
  state = next;
  if (state.auth_mode === 'demo' && !demoCatalog.length) demoCatalog = (await api('demo/scenarios')).scenarios;
  if (version !== protectedVersion) return;
  document.body.classList.remove('signed-out');
  $('#sign-out').hidden = state.auth_mode !== 'firebase';
  $('#persona').hidden = state.auth_mode !== 'demo';
  document.querySelector('.persona-label').hidden = state.auth_mode !== 'demo';
  $('#project-name').textContent = state.project.name;
  $('#persona').value = state.role; $('#persona').disabled = state.auth_mode !== 'demo';
  $('#profile-initial').textContent = roleNames[state.role][0];
  $('#profile-label').innerHTML = `${roleNames[state.role]}<small>${state.auth_mode === 'demo' ? 'Demo persona' : 'Verified member'}</small>`;
  $('#mode').textContent = state.ai_mode === 'offline' ? '● Offline rehearsal' : '● Gemini configured';
  $('#footer-mode').textContent = state.auth_mode === 'demo' ? 'Synthetic data · Isolated demo sandbox' : 'Authenticated workspace';
  if (activeRun) activeRun = state.tasks.find(t => t.id === activeRun.id);
  render();
}
function heading(eyebrow, title, subtitle, action = '') {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p class="subtitle">${subtitle}</p></div>${action}</div>`;
}
function empty(title, description, action = '', glyph = 'spark') {
  return `<div class="empty">${icon(glyph)}<h3>${title}</h3><p>${description}</p>${action}</div>`;
}
function btn(label, action, primary = false, attrs = '') {
  return `<button class="btn ${primary ? 'primary' : ''}" data-action="${action}" ${attrs}>${label}</button>`;
}
function viewFromUrl() {
  const view = location.hash.slice(1);
  return resolveView(view || (location.pathname === '/knowledge' ? 'knowledge' : 'overview'));
}
function syncViewUrl() {
  const path = currentView === 'knowledge' ? '/knowledge' : location.pathname === '/knowledge' ? '/' : null;
  if (path === null) return;
  const url = path + location.search + (currentView === 'knowledge' ? '' : '#' + currentView);
  if (location.pathname + location.search + location.hash !== url) history.replaceState(history.state, '', url);
}
function go(view) {
  const target = resolveView(view);
  if (currentView === target) render(); else location.hash = target;
}
function formatTime(value) { return new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}); }
function eventRows(events) {
  return events.map(e => `<div class="activity"><span class="activity-marker">${e.action.includes('published') ? '✓' : '↗'}</span><div><strong>${esc(e.action)}</strong><p>${esc(e.detail)}</p><small>${esc(e.actor)}${e.role ? ` · ${roleNames[e.role]}` : ''} · ${esc(e.outcome || 'completed')}</small></div><time datetime="${esc(e.at)}">${formatTime(e.at)}</time></div>`).join('');
}
function stat(label, value, description, glyph) { return `<div class="stat"><div class="stat-top"><span>${label}</span>${icon(glyph)}</div><div class="stat-value">${value}</div><div class="stat-foot">${description}</div></div>`; }
function render() {
  if (!state) return;
  window.contextPages.clear();
  currentView = resolveView(currentView);
  syncViewUrl();
  const attention = attentionCount();
  const link = ([id,label,glyph]) => `<a href="${id === 'knowledge' ? '/knowledge' : '#' + id}" class="nav-item ${currentView === id ? 'active' : ''}" ${currentView === id ? 'aria-current="page"' : ''} title="${label}">${icon(glyph)}<span class="nav-text">${label}</span>${id === 'inbox' && attention ? `<span class="nav-badge" aria-label="${attention} items need your attention">${attention}</span>` : ''}</a>`;
  $('#nav').innerHTML = navItems.map(link).join('');
  const tools = secondaryItems.filter(([id]) => id !== 'demo' || state.auth_mode === 'demo').map(link).join('');
  $('#secondary-nav').innerHTML = tools;
  $('#mobile-tools').innerHTML = tools;
  $('#crumb').textContent = viewLabel(currentView);
  $('#main').innerHTML = ({overview, work, knowledge, inbox, insights, demo})[currentView]();
  if (currentView === 'knowledge' && state.context_pages_enabled) window.contextPages.mount($('#context-pages'), async () => {toast('Proposal created. Open project proposals for independent review.');}, message => showSignIn(message));
  else if (currentView === 'knowledge') $('#search').value = queryFilter;
}
function canReview(proposal) {
  return proposal.status === 'pending' && state.role === owners[proposal.domain] && state.actor !== proposal.author;
}
function affectedRuns() {
  return state.tasks.filter(t => t.stale && (t.actor ? t.actor === state.actor : t.role === state.role));
}
function attentionCount() {
  return state.proposals.filter(canReview).length + affectedRuns().length;
}
function overviewAttention() {
  const contexts = new Map(state.contexts.map(c => [c.id,c]));
  const items = affectedRuns().slice().reverse().map(t => {
    const required = t.manifest.sources.filter(s => contexts.get(s.id)?.mandatory && contexts.get(s.id).revision !== s.revision);
    return {priority:required.length ? 0 : 2, label:required.length ? 'Critical' : 'Needs review',
      title:t.query, detail:required.length ? `Required context changed: ${required.map(s => `${s.id} v${s.revision} → v${contexts.get(s.id).revision}`).join(', ')}. Check this work before continuing.` : 'An accepted source or dependency changed after this run.',
      button:'Inspect run', action:'open-run', attrs:`data-id="${esc(t.id)}"`};
  });
  for (const p of state.proposals.filter(p => p.status === 'pending')) {
    const current = contexts.get(p.context_id);
    const conflict = current && current.revision !== p.base_revision;
    if (!canReview(p) && !(conflict && p.author === state.actor)) continue;
    items.push({priority:1, label:conflict ? 'Conflict' : 'Review', title:p.title,
      detail:conflict ? `Based on v${p.base_revision}; accepted context is now v${current.revision}. A new proposal is needed.` : `${roleNames[owners[p.domain]]} review requested by ${p.author}.`,
      button:'View proposal', action:'navigate', attrs:`data-view="inbox" data-filter="${canReview(p) ? 'mine' : 'pending'}"`});
  }
  if (state.usage.at(-1)?.status === 'failed') items.push({priority:1, label:'Call failed',
    title:'Latest model attempt failed', detail:'Check activity and usage before retrying the task.',
    button:'View activity', action:'navigate', attrs:'data-view="insights"'});
  return items.sort((a,b) => a.priority - b.priority);
}
function overview() {
  const items = overviewAttention(), critical = items.filter(item => item.priority === 0).length;
  const accepted = state.contexts.filter(c => c.status === 'accepted');
  const pending = state.proposals.filter(p => p.status === 'pending').length;
  const stale = state.tasks.filter(t => t.stale).length;
  const required = accepted.filter(c => c.mandatory).length;
  const status = critical ? `${critical} critical ${critical === 1 ? 'item' : 'items'}` : items.length ? 'Needs attention' : 'No actions flagged';
  const summary = critical ? 'Required context changed in your earlier work.' : items.length ? `${items.length} ${items.length === 1 ? 'item needs' : 'items need'} your attention.` : accepted.length ? 'Your review queue and recorded runs have no flagged actions.' : 'Start by adding your project’s shared knowledge.';
  return heading('PROJECT OVERVIEW',esc(state.project.name),'Shared decisions, reviews and work at a glance.',btn('Refresh overview','refresh-overview'))+
    `<section class="overview-status ${critical ? 'is-critical' : ''}" aria-label="Your attention summary"><div><span class="tag ${critical ? 'critical' : items.length ? 'amber' : ''}">${status}</span><h2>${summary}</h2><p>Showing project information available to you · ${roleNames[state.role]}</p></div><div class="button-group">${btn(`${icon('plus')} Start a task`,'navigate',true,'data-view="work"')}${btn('Browse knowledge','navigate',false,'data-view="knowledge"')}</div></section>`+
    `<div class="stats">${stat('Accepted topics',accepted.length,'Shared project knowledge','knowledge')}${stat('Pending proposals',pending,'Awaiting independent review','reviews')}${stat('Affected runs',stale,'Visible runs with changed context','branch')}${stat('Required constraints',required,'Included in context assembly','shield')}</div>`+
    `<div class="grid-2 overview-grid"><section class="panel" aria-labelledby="attention-title"><div class="panel-head"><div><h2 id="attention-title">Needs your attention</h2><p>Changed required context comes first.</p></div><span class="tag">${items.length} ${items.length === 1 ? 'item' : 'items'}</span></div>${items.length ? `<ul class="overview-attention">${items.slice(0,6).map(item => `<li class="overview-attention-item"><div><span class="tag ${item.priority === 0 ? 'critical' : 'amber'}">${item.label}</span><h3>${esc(item.title)}</h3><p>${esc(item.detail)}</p></div>${btn(item.button,item.action,false,item.attrs)}</li>`).join('')}</ul>${items.length > 6 ? `<p class="overview-more">Showing the first 6 of ${items.length} items. Open Inbox for reviews and affected runs.</p>` : ''}` : empty(accepted.length ? 'Nothing needs your attention' : 'No shared knowledge yet',accepted.length ? 'Start a task or explore your team’s accepted decisions.' : 'Add requirements or decisions for an independent owner to review.',accepted.length ? btn('Start a task','navigate',true,'data-view="work"') : btn('Add knowledge','ingest',true),'check')}<div class="panel-bottom">${btn('Open Inbox','navigate',false,'data-view="inbox" data-filter="pending"')}</div></section>`+
    `<section class="panel" aria-labelledby="recent-activity-title"><div class="panel-head"><div><h2 id="recent-activity-title">Recent activity</h2><p>Latest changes and outcomes you can access.</p></div>${icon('clock')}</div><div class="panel-body">${state.events.length ? eventRows(state.events.slice(0,5)) : empty('No activity yet','Changes and task outcomes will appear here.','','clock')}</div><div class="panel-bottom">${btn('View all activity','navigate',false,'data-view="insights"')}</div></section></div>`;
}
function filteredKnowledge() {
  const query = queryFilter.trim().toLowerCase();
  return state.contexts.filter(c => (domainFilter === 'All domains' || c.domain === domainFilter)
    && `${c.id} ${c.title} ${c.body}`.toLowerCase().includes(query));
}
function knowledgeResults(list) {
  return (list.length ? `<div class="context-grid">${list.map(c => `<button class="context-card" data-action="context" data-id="${esc(c.id)}"><span class="card-meta"><span class="tag ${c.policy === 'Restricted' ? 'purple' : 'green'}">${esc(c.domain)}</span><span class="version">v${c.revision}</span></span><h3>${esc(c.title)}</h3><p>${esc(c.body)}</p><span class="card-footer"><span>${esc(c.id)} · ${roleNames[c.owner]}</span><span>${c.mandatory ? '● Required' : c.policy === 'Restricted' ? '● Restricted' : '✓ Accepted'}</span></span></button>`).join('')}</div>` : empty('No matching knowledge','Try a broader search or choose another domain.'));
}
function updateKnowledgeResults() {
  const list = filteredKnowledge();
  $('#knowledge-results').innerHTML = knowledgeResults(list);
  $('#knowledge-count').textContent = `${list.length} context items`;
}
function knowledge() {
  if (state.context_pages_enabled) return '<div class="cp-page-heading"><h1>Shared knowledge</h1><p>Explore the map. Open a context to focus on its content.</p></div>' + '<div id="context-pages"><div class="loading">Loading shared knowledge…</div></div>';
  const list = filteredKnowledge();
  return heading('SHARED KNOWLEDGE','Find a decision.','Open a topic to inspect or propose a change.',btn(`${icon('plus')} Add knowledge`,'ingest',true))+
  `<div class="toolbar"><div class="search"><input id="search" type="search" placeholder="Search decisions, requirements, or source IDs…" aria-label="Search shared knowledge"></div><select id="domain-filter" aria-label="Filter by domain">${['All domains',...Object.keys(owners)].map(d => `<option ${d === domainFilter ? 'selected' : ''}>${d}</option>`).join('')}</select><span class="muted" id="knowledge-count" aria-live="polite">${list.length} context items</span></div><div id="knowledge-results">${knowledgeResults(list)}</div>`;
}
const demoPersonas = {
 pm: {title:'Product manager',initial:'PM',focus:'Preserve the business intent',authority:'Owns requirements; reviews product scope and acceptance criteria.'},
 architect: {title:'Architect',initial:'AR',focus:'Keep the design coherent',authority:'Owns architecture; reviews design changes and tradeoffs.'},
 developer: {title:'Developer',initial:'DE',focus:'Build with accepted context',authority:'Uses requirements and architecture; proposes discoveries for review.'},
 qa: {title:'QA engineer',initial:'QA',focus:'Verify the right outcome',authority:'Owns quality knowledge; checks scenarios and stale test assumptions.'},
 security: {title:'Security',initial:'SE',focus:'Protect knowledge boundaries',authority:'Owns security rules and can inspect explicitly restricted findings.'}
};
function demo() {
  if (state.auth_mode !== 'demo') return heading('DEMO CENTER','A guided view of ContextOS.','Synthetic multi-persona scenarios are available only in demo mode.') + '<div class="note">Your authenticated workspace does not allow persona impersonation. Use a separately configured synthetic demo instance to run these walkthroughs.</div>';
  const list = demoCatalog.filter(s => (demoRole === 'all' || s.roles.includes(demoRole)) && (demoCategory === 'All cases' || s.category === demoCategory));
  if (!list.some(s => s.id === demoSelected) && list.length) demoSelected = list[0].id;
  const selected = list.find(s => s.id === demoSelected);
  const results = Object.values(demoReports);
  const passed = results.filter(r => r.passed).length;
  const failed = results.length - passed;
  const personas = Object.entries(demoPersonas).map(([role,p]) => `<button class="demo-persona ${demoRole===role?'selected':''}" data-action="demo-persona" data-role="${role}" aria-pressed="${demoRole===role}"><span class="demo-avatar">${p.initial}</span><strong>${p.title}</strong><span>${p.focus}</span><small>${p.authority}</small></button>`).join('');
  const report = selected && demoReports[selected.id];
  return heading('INTERACTIVE DEMO','See the handoff happen.','Choose a case. Walk through one action at a time.',btn(demoRunning ? 'Checking scenarios…' : `${icon('check')} Verify all ${demoCatalog.length} cases`,'demo-all',true,demoRunning?'disabled':'')) +
    `<div class="demo-summary"><span class="tag green">${passed}/${demoCatalog.length} verified</span><span>Isolated rehearsal · Your workspace stays intact</span></div>`+
    `<details class="demo-persona-picker"><summary>Filter by persona${demoRole==='all'?'':` · ${demoPersonas[demoRole].title}`}</summary><div class="demo-section-head"><h2>Choose a perspective</h2><button class="text-btn" data-action="demo-persona" data-role="all" aria-pressed="${demoRole==='all'}">Show all personas</button></div><div class="demo-personas">${personas}</div></details>`+
    `<div class="demo-section-head"><div><h2>Explore the solution</h2><p class="muted">${list.length} cases${demoRole==='all'?' across the team':` involving ${demoPersonas[demoRole].title}`}</p></div><select id="demo-category" aria-label="Demo case category">${['All cases',...new Set(demoCatalog.map(s=>s.category))].map(category=>`<option${category===demoCategory?' selected':''}>${category}</option>`).join('')}</select></div>`+
    `<div class="demo-workbench"><section class="panel demo-case-list" aria-label="Demo scenarios">${list.length?list.map(s=>`<button class="demo-case ${s.id===demoSelected?'selected':''}" data-action="demo-select" data-id="${s.id}" aria-pressed="${s.id===demoSelected}"><span class="demo-case-label"><span class="tag">${s.category}</span><span class="demo-case-status">${demoReports[s.id] ? (demoReports[s.id].passed?'✓ Passed':'! Needs attention') : 'Not run'}</span></span><strong>${s.title}</strong></button>`).join(''):empty('No cases in this combination','Choose All cases or show all personas.')}</section><section class="panel demo-detail">${selected ? `<div class="form-panel"><div class="eyebrow">${selected.category.toUpperCase()} WALKTHROUGH</div><h2 class="demo-detail-title">${selected.title}</h2><div class="demo-cast">${selected.roles.map(role=>`<span class="tag green">${demoPersonas[role].title}</span>`).join('<span class="muted">→</span>')}</div><div class="button-group">${btn(demoRunning ? 'Running…' : report ? 'Restart walkthrough' : 'Start walkthrough','demo-run',true,`data-id="${selected.id}" ${demoRunning?'disabled':''}`)}${btn('Try in workspace ↗','demo-try',false,`data-id="${selected.id}" ${demoRunning?'disabled':''}`)}</div>${report ? demoStep(selected,report) : `<div class="demo-ready">${icon('branch')}<h3>Follow the decision, step by step.</h3><p>Start, then use Next to reveal each persona’s action.</p></div>`}<p class="form-help">Try in workspace opens ${viewLabel(selected.view)} as ${demoPersonas[selected.role].title}.</p></div>` : empty('Choose a case','Select another category to continue.')}</section></div>`+
    `<details class="panel gap-top demo-limits"><summary>Demo scope & cloud status</summary><div class="panel-head"><div><h2>Coverage</h2><p>Local behavior and cloud readiness are tracked separately.</p></div></div><div class="demo-coverage"><div><span class="tag green">Available locally</span><p>Shared knowledge, note candidates, manual authoring, independent review, exact snapshots, restricted access, conflicts, rollback, dependency alerts and usage transparency.</p></div><div><span class="tag amber">Awaiting cloud setup</span><p>Live Gemini reasoning and extraction, real Firebase accounts, Firestore persistence across instances, and Google Cloud deployment.</p></div><div><span class="tag">Future roadmap</span><p>Semantic search, MCP and IDE access, repository synchronization, automatic knowledge consolidation, and enterprise administration.</p></div></div></details>`;
}
function demoStep(scenario, report) {
  const index = demoPositions[scenario.id] || 0, step = report.steps[index];
  const persona = demoPersonas[step.role] || demoPersonas[scenario.role];
  const checkpoint = step.checkpoint;
  const previous = index > 0 ? report.steps[index-1].checkpoint : null;
  const done = demoCompleted[scenario.id];
  const next = report.steps[index+1];
  return `<section class="demo-stage" aria-label="Current walkthrough step" tabindex="-1">
    <div class="demo-progress"><span>Step ${index+1} of ${report.steps.length}</span><span>${persona.title}</span></div>
    <progress max="${report.steps.length}" value="${index+1}" aria-label="Walkthrough progress"></progress>
    <div class="demo-stage-heading"><span class="demo-avatar">${persona.initial}</span><div><small>ACTING PERSONA · ${persona.title}</small><h3>${esc(step.title)}</h3></div></div>
    <p class="demo-step-detail">${esc(step.detail)}</p>
    <div class="note ${step.passed?'':'amber'}">${step.passed?'✓ Expected outcome verified':'! Check needs attention'}</div>
    ${checkpoint ? `<details class="demo-checkpoint"><summary>Inspect knowledge at this step</summary><p class="muted">Accepted revisions visible to ${persona.title}. Highlighted rows changed since the previous step.</p><div class="demo-ledger">${checkpoint.accepted_context.map(item=>{
      const prior = previous?.accepted_context.find(c=>c.id===item.id);
      const changed = previous && (!prior || prior.revision!==item.revision);
      return `<details class="demo-ledger-row ${changed?'changed':''}"><summary><span>${esc(item.title)}</span><span class="version">${changed && prior ? `v${prior.revision} → ` : ''}v${item.revision}</span></summary><p>${esc(item.body)}</p><small>${esc(item.id)}</small></details>`;
    }).join('')}</div>${checkpoint.proposals.length ? `<div class="demo-proposal-state"><strong>Review queue</strong>${checkpoint.proposals.map(p=>`<p>${esc(p.title)} <span class="tag ${p.status==='pending'?'amber':'green'}">${esc(p.status)}</span></p>`).join('')}</div>`:''}${checkpoint.stale_runs?`<div class="note amber">${checkpoint.stale_runs} prior run needs review.</div>`:''}</details>`:''}
    <div class="demo-step-controls">${btn('← Back','demo-back',false,`data-id="${scenario.id}" ${index===0?'disabled':''}`)}<span class="muted">${done?'Walkthrough complete':index===report.steps.length-1?'Final step':`Next: ${demoPersonas[next.role]?.title || 'Continue'}`}</span>${btn(index===report.steps.length-1?'Finish walkthrough':'Next step →',index===report.steps.length-1?'demo-finish':'demo-next',true,`data-id="${scenario.id}" ${done?'disabled':''}`)}</div>
    <details class="history"><summary>Step activity · ${index+1} actions revealed</summary>${report.steps.slice(0,index+1).map(s=>`<div class="history-entry"><strong>${esc(s.title)}</strong><small>${esc(s.actor || `demo-${s.role}`)} · ${demoPersonas[s.role]?.title || 'Scenario'} · ${s.passed?'verified':'needs attention'}${s.at ? ` · ${formatTime(s.at)}` : ''}</small></div>`).join('')}</details>
    ${done?`<div class="note" role="status">${report.passed?'Walkthrough complete. Every checkpoint passed.':'Walkthrough complete. Review the failed checks.'}</div><details class="history"><summary>Inspect complete scenario evidence</summary><pre class="demo-evidence">${esc(JSON.stringify(report.evidence,null,2))}</pre></details>`:''}
  </section>`;
}
function focusDemoStep() {
  const stage = document.querySelector('.demo-stage');
  if (stage) {stage.focus({preventScroll:true}); stage.scrollIntoView({block:'start',behavior:'instant'});}
}
async function runDemoCase(id) {
  try {demoReports[id] = await api(`demo/scenarios/${id}`,{}); demoPositions[id] = 0; demoCompleted[id] = false;}
  catch(error) {demoReports[id] = {passed:false,steps:[{title:'Scenario could not complete',passed:false,detail:error.message}],evidence:{}};}
}

function runOutput(run) {
  return `<section class="panel result"><div class="form-panel"><div class="result-head"><div><h2>${run.stale ? 'Context has changed' : 'Your task briefing'}</h2><small>${roleNames[run.role]} · ${formatTime(run.created_at)} · ${esc(run.id)}</small></div><span class="tag ${run.stale ? 'amber' : 'green'}">${run.stale ? 'Needs review' : 'Current snapshot'}</span></div>${run.stale ? '<div class="note amber">An accepted dependency changed. This output remains tied to its original sources. Rerun to adopt current knowledge.</div>' : ''}<div class="prose">${esc(run.output)}</div><div class="dialog-actions">${btn('Inspect context','manifest',false,`data-id="${esc(run.id)}"`)}${btn('Rerun with latest context','rerun',false,`data-id="${esc(run.id)}"`)}</div></div></section>`;
}
function taskRows(list) {
  return list.map(t => `<div class="task-row"><div><strong>${esc(t.query)}</strong><small>${roleNames[t.role]} · ${t.manifest.sources.length} sources · ${formatTime(t.created_at)}</small></div><div class="button-group"><span class="tag ${t.stale ? 'amber' : 'green'}">${t.stale ? 'Needs review' : 'Current'}</span>${btn('Open run','open-run',false,`data-id="${esc(t.id)}"`)}</div></div>`).join('');
}
function taskSources() {
  return `<aside class="panel task-sources"><div class="panel-head"><h2>${activeRun ? 'Decisions used' : 'Shared project knowledge'}</h2>${icon('shield')}</div><div class="panel-body">${activeRun ? `<p class="source-intro">${activeRun.stale ? 'Original sources · a newer decision needs review.' : 'These accepted revisions informed this run.'}</p><div class="source-list">${activeRun.manifest.sources.map(s => `<div class="source-item"><strong>${esc(s.title)}</strong><small>${esc(s.id)} · v${s.revision}</small></div>`).join('') || '<p class="muted">No accepted sources were supplied to this run.</p>'}</div>${btn('Inspect exact sources','manifest',false,`data-id="${esc(activeRun.id)}"`)}` : `<p class="source-intro">Your task uses relevant accepted decisions. After a run, inspect the exact sources here.</p>${btn('Browse knowledge','navigate',false,'data-view="knowledge"')}`}</div></aside>`;
}
function work() {
  const list = state.tasks.slice().reverse();
  const attention = attentionCount();
  const budget = sessionStorage.getItem('task-budget') || '6000';
  return heading('WORK','What are you working on?','Start a task with your team’s accepted decisions.')+
  `<div class="workspace-summary"><span>${roleNames[state.role]} · ${state.contexts.length} accepted topics</span>${attention ? btn(`${attention} items need your attention`,'navigate',false,'data-view="inbox"') : ''}</div>`+
  `<div class="workbench"><div><section class="panel"><form id="task-form" class="form-panel"><label class="field" for="task-query">Task goal<textarea id="task-query" name="query" required minlength="3" maxlength="2000" placeholder="Describe your task or the decision you need help with…">${esc(sessionStorage.getItem('task-draft') || '')}</textarea></label><details class="task-options"><summary>Advanced options</summary><label class="field">Context budget<select name="budget" id="task-budget">${['6000','3000','1000','12000'].map(value => `<option value="${value}" ${value === budget ? 'selected' : ''}>${Number(value).toLocaleString()} estimated tokens</option>`).join('')}</select></label><p class="form-help">Source-only budget uses conservative byte estimates. Instructions, task text, and output are outside this budget.</p></details><div class="task-actions"><button class="btn primary" type="submit">${icon('spark')} ${state.ai_mode === 'offline' ? 'Run rehearsal' : 'Ask Gemini'}</button><button type="button" class="text-btn" data-action="task-suggestion">Use a suggested task</button></div><p class="form-help">${state.ai_mode === 'offline' ? 'Offline rehearsal · deterministic source briefing.' : 'Gemini drafts work. Shared decisions still require review.'}</p></form></section>${activeRun ? runOutput(activeRun) : ''}</div>${taskSources()}</div>`+
  `<section class="panel gap-top"><div class="panel-head"><div><h2>Recent work</h2><p>Open a run to inspect its answer and sources.</p></div><span class="tag">${list.length} runs</span></div>${list.length ? taskRows(list) : empty('Your first task starts here','Describe what you need help with above.')}</section>`;
}
function inbox() {
  const pending = state.proposals.filter(p => p.status === 'pending');
  const mine = pending.filter(canReview);
  const history = state.proposals.filter(p => p.status !== 'pending');
  const stale = affectedRuns();
  const list = [...({pending,mine,history})[inboxFilter]].reverse().sort((a,b) => Number(canReview(b)) - Number(canReview(a)));
  return heading('INBOX','What needs attention?','Review proposals and revisit work affected by changed decisions.')+
    (stale.length ? `<section class="panel inbox-alerts"><div class="panel-head"><div><h2>Changed context</h2><p>Your earlier runs still use their original sources. Review before refreshing.</p></div><span class="tag amber">${stale.length} affected</span></div>${taskRows(stale.slice().reverse())}</section>` : '')+
    `<div class="inbox-heading"><h2>Proposals</h2><div class="button-group inbox-filters" role="group" aria-label="Filter proposals">${[['pending','Pending',pending.length],['mine','For my review',mine.length],['history','History',history.length]].map(([id,label,count]) => btn(`${label} (${count})`,'inbox-filter',inboxFilter === id,`data-filter="${id}" aria-pressed="${inboxFilter === id}"`)).join('')}</div></div>`+reviewCards(list);
}
function reviewCards(list) {
  return (list.length ? list.map(p => {
    const can = canReview(p);
    return `<details class="panel review-card" id="proposal-${esc(p.id)}" ${p.status === 'pending' ? 'open' : ''}><summary class="review-summary">${esc(p.title)} <span class="tag">${esc(p.status)}</span></summary><div class="review-top"><div><span class="tag ${p.status === 'pending' ? 'amber' : 'green'}">${esc(p.status)}</span><h3>${esc(p.title)}</h3><p>${esc(p.author)} → ${roleNames[owners[p.domain]]} · ${esc(p.context_id || p.published_context_id || 'New context')} ${p.base_revision ? `· Based on v${p.base_revision}` : ''}</p></div><span class="tag">${esc(p.domain)}</span></div><p class="muted">${esc(p.reason)}</p><div class="diff gap-top"><div class="diff-pane"><strong>ACCEPTED BASE ${p.base_revision ? `· V${p.base_revision}` : ''}</strong><pre>${esc(p.before || 'New topic — no accepted version yet.')}</pre></div><div class="diff-pane after"><strong>PROPOSED CHANGE</strong><pre>${esc(p.body)}</pre></div></div><div class="review-actions"><p>${p.status !== 'pending' ? `Reviewed by ${esc(p.reviewer)}` : can ? 'Your approval publishes exactly this proposal.' : state.actor === p.author ? 'Independent review required; the author cannot self-approve.' : `Awaiting an independent ${roleNames[owners[p.domain]]} reviewer.`}</p>${can ? btn('Reject','reject',false,`data-id="${esc(p.id)}"`)+btn(`${icon('check')} Approve & publish`,'approve',true,`data-id="${esc(p.id)}"`) : ''}</div></details>`;
  }).join('') : `<section class="panel">${empty('No proposals in this view','Browse shared knowledge to propose a change, or choose another filter.',btn('Browse knowledge','navigate',false,'data-view="knowledge"'),'reviews')}</section>`);
}
function insights() {
  const liveUsage = state.usage.filter(u => u.provider && u.provider !== 'offline');
  const failedUsage = state.usage.filter(u => u.status === 'failed').length;
  const total = liveUsage.reduce((n,u) => n + (u.total_tokens || 0), 0);
  const stale = state.tasks.filter(t => t.stale).length;
  return heading('ACTIVITY & INSIGHTS','Who did what.','Inspect actions, sources, and change impact.',btn('Export evidence','export'))+
  `<div class="stats">${stat('Source snapshots',state.tasks.length,'Exact input manifests','knowledge')}${stat('Stale runs',stale,'Explicit dependency impact','branch')}${stat('Live model calls',liveUsage.length,'Excludes offline rehearsals','spark')}${stat('Provider tokens',total.toLocaleString(),'Reported totals across live calls','insights')}</div>`+
  `<div class="grid-2"><section class="panel"><div class="panel-head"><div><h2>Knowledge dependencies</h2><p>Changes travel through these explicit links.</p></div>${icon('branch')}</div><div class="panel-body">${state.contexts.filter(c => c.dependencies.length).map(c => `<div class="dependency"><button data-action="context" data-id="${esc(c.id)}">${esc(c.id)}</button><span>depends on</span>${c.dependencies.filter(id => state.contexts.some(c => c.id === id)).map(id => `<button data-action="context" data-id="${esc(id)}">${esc(id)}</button>`).join('')}</div>`).join('')}<div class="note">Publishing a source revision flags runs that used it or an explicitly linked downstream context. Review and rerun to adopt the update.</div></div></section><section class="panel"><div class="panel-head"><h2>Measurement, with receipts</h2>${icon('insights')}</div><div class="panel-body"><p class="prose">Context estimates compare selected knowledge with all visible accepted knowledge. They do not measure end-to-end savings or response quality.</p><div class="note">Live provider telemetry includes extraction and task calls. Offline rehearsal consumes zero model tokens. ${failedUsage} failed call(s). Any available provider usage is included even if output validation or persistence failed. Missing usage must be investigated before making cost claims.</div></div></section></div>`+
  `<section class="panel"><div class="panel-head"><h2>Retrieval evidence</h2><span class="tag">Context estimates only</span></div>${state.tasks.length ? `<div class="table-wrap"><table><thead><tr><th>Task</th><th>Sources</th><th>Selected estimate</th><th>Full-context estimate</th><th>Status</th></tr></thead><tbody>${state.tasks.slice().reverse().map(t => `<tr><td><button class="text-btn" data-action="manifest" data-id="${esc(t.id)}">${esc(t.query.slice(0,48))}</button></td><td>${t.manifest.sources.length}</td><td>${t.manifest.estimated_tokens.toLocaleString()}</td><td>${t.manifest.baseline_estimated_tokens.toLocaleString()}</td><td><span class="tag ${t.stale ? 'amber' : 'green'}">${t.stale ? 'Stale' : 'Current'}</span></td></tr>`).join('')}</tbody></table></div>` : empty('Evidence arrives with every run','Start an agent task to collect a source manifest and context estimates.','','insights')}</section>`+
  `<section class="panel gap-top"><div class="panel-head"><h2>Persona activity</h2><span class="tag">${state.events.length} visible events</span></div><div class="panel-body">${eventRows(state.events)}</div></section>`;
}
function modal(title, subtitle, body) {
  $('#dialog-content').innerHTML = `<div class="dialog-head"><div><h2 id="dialog-title">${title}</h2><p>${subtitle}</p></div><button class="close" data-action="close" aria-label="Close dialog">×</button></div><div class="dialog-body">${body}</div>`;
  if (!$('#dialog').open) $('#dialog').showModal();
}
async function openContext(id) {
  const c = state.contexts.find(c => c.id === id); if (!c) return;
  await api('activity',{action:'context_viewed',target_id:id});
  selectedContext = c;
  modal(esc(c.title),`${esc(c.id)} · ${esc(c.domain)} · ${roleNames[c.owner]} · Accepted v${c.revision}`,
    `<div class="button-group"><span class="tag green">Accepted</span><span class="tag">${esc(c.policy)} policy</span>${c.mandatory ? '<span class="tag amber">Mandatory constraint</span>' : ''}</div><div class="prose gap-top">${esc(c.body)}</div><div class="note">Source: ${c.sources.map(esc).join(', ')}${c.dependencies.length ? `<br>Depends on: ${c.dependencies.map(esc).join(', ')}` : ''}</div><div class="dialog-actions">${btn('Propose a change','edit',true)}</div><details class="history"><summary>Revision history · ${c.history.length} versions</summary>${c.history.slice().reverse().map(h => `<div class="history-entry"><strong class="tag">v${h.revision}</strong><small>${esc(h.actor)} · ${new Date(h.at).toLocaleString()}</small><p>${esc(h.body)}</p><small>${esc(h.reason)}</small>${h.revision !== c.revision ? btn(`Propose restoring v${h.revision}`,'restore',false,`data-revision="${h.revision}"`) : ''}</div>`).join('')}</details>`);
}
function editContext(body, reason = '') {
  const c = selectedContext;
  modal(`Propose a change`,`${esc(c.title)} · Based on accepted v${c.revision}`,
  `<form id="proposal-form"><label class="field">Proposed content<textarea class="tall" name="body" required maxlength="10000">${esc(body ?? c.body)}</textarea></label><label class="field">Why should this change?<textarea name="reason" required maxlength="1500" placeholder="Explain the discovery, tradeoff, or requirement behind this revision…">${esc(reason)}</textarea></label><div class="note">This leaves v${c.revision} accepted until an independent ${roleNames[c.owner]} approves your exact proposal.</div><button class="btn primary" type="submit">Send for review ${icon('arrow')}</button></form>`);
}
async function manifest(id) {
  await api('activity',{action:'manifest_inspected',target_id:id});
  const t = state.tasks.find(t => t.id === id); if (!t) return;
  modal('Context used',`${esc(t.id)} · ${t.manifest.sources.length} sources · ${t.manifest.estimated_tokens.toLocaleString()} estimated tokens`,
    `<div class="note ${t.stale ? 'amber' : ''}">${t.stale ? 'This run is affected by a newer accepted decision. These are the exact original inputs.' : 'These are the exact accepted source bodies supplied to this run.'}</div>${t.manifest.sources.map(s => `<details class="history"><summary>${esc(s.id)} · v${s.revision} · ${esc(s.title)}</summary><div class="prose gap-top">${esc(s.body)}</div></details>`).join('')}<p class="form-help">Estimator: ${esc(t.manifest.estimator)}. Context budget: ${t.manifest.budget}. Model: ${esc(t.usage.model || 'Offline rehearsal')}. Provider-reported total: ${t.usage.total_tokens ?? 'unavailable'}.</p>`);
}
async function runTask(query,budget) {
  const run = await api('tasks',{query,budget}); activeRun = run;
  await refresh(); go('work'); toast('Task saved with its source manifest.');
}
function addKnowledge() {
  modal('Bring knowledge into the workspace','Extract a candidate from notes or write a topic directly. Both require review.',
    `<div class="button-group" role="group" aria-label="Knowledge authoring mode"><button class="btn primary" data-action="knowledge-mode" data-mode="extract" aria-pressed="true">Extract from notes</button><button class="btn" data-action="knowledge-mode" data-mode="manual" aria-pressed="false">Manual proposal</button></div>
    <form id="ingest-form" class="gap-top"><label class="field">Stakeholder notes<textarea class="tall" name="notes" required minlength="10" maxlength="8000" placeholder="Paste a decision, requirement, or meeting note…"></textarea></label><label class="field">Source reference<input name="source" required maxlength="200" placeholder="e.g. Product workshop, 14 October"></label><div class="note">${state.ai_mode === 'offline' ? 'Offline mode preserves your notes verbatim as a requirement candidate. Gemini extraction becomes available when configured.' : 'Gemini extracts one candidate topic. Nothing is accepted until human review.'}</div><button type="submit" class="btn primary">${icon('spark')} Create review candidate</button></form>
    <form id="manual-proposal-form" class="gap-top" hidden><label class="field">Topic title<input name="title" required maxlength="120"></label><label class="field">Domain<select name="domain">${Object.keys(owners).map((domain,index) => `<option${index === 0 ? ' selected' : ''}>${domain}</option>`).join('')}</select></label><label class="field">Proposed content<textarea name="body" required maxlength="10000" class="tall"></textarea></label><label class="field">Reason for this topic<input name="reason" required maxlength="1500"></label><label class="field">Source reference<input name="source" required maxlength="200"></label><div class="note">No model call is needed. An independent reviewer who owns this domain must approve your proposal. New topics use the Reviewed policy and are visible to project members after publication.</div><button type="submit" class="btn primary">Send manual proposal for review</button></form>`);
}
function clearProtectedView() {
  protectedVersion++;
  window.contextPages.clear();
  state = undefined; activeRun = undefined; selectedContext = undefined;
  queryFilter = ''; domainFilter = 'All domains'; inboxFilter = 'pending';
  demoCatalog = []; demoReports = {}; demoPositions = {}; demoCompleted = {};
  sessionStorage.removeItem('task-draft');
  sessionStorage.removeItem('task-budget');
  $('#dialog').close(); $('#dialog-content').replaceChildren();
  $('#main').replaceChildren(); $('#nav').replaceChildren();
  $('#secondary-nav').replaceChildren();
  $('#mobile-tools').replaceChildren(); $('#workspace-tools').open = false;
  $('#project-name').textContent = ''; $('#profile-label').textContent = '';
  $('#sign-out').hidden = true;
}
function showSignIn(message='') {
  clearProtectedView();
  document.body.classList.add('signed-out');
  const ready = identityConfig?.login_ready;
  $('#main').innerHTML = `<section class="auth-panel"><div class="auth-intro"><a class="brand" href="#overview">ContextOS</a><div class="eyebrow">SHARED KNOWLEDGE. CLEAR OWNERSHIP.</div><h1>Your workspace,<br>with the right access.</h1><p>Sign in to continue with your team’s accepted decisions.</p><span class="tag">Firebase · Protected session</span></div><div class="auth-form-panel"><h2>Sign in</h2><p class="subtitle">Use your administrator-provisioned account.</p>${message ? `<div class="note amber" role="alert">${esc(message)}</div>` : ''}${!ready ? '<div class="note">Firebase sign-in is awaiting project configuration. Ask your administrator to enable email/password sign-in and set the public Web API key.</div>' : ''}<form id="login-form" class="gap-top"><label class="field">Email<input type="email" name="email" autocomplete="username" required maxlength="254" ${ready?'':'disabled'}></label><label class="field">Password<input type="password" name="password" autocomplete="current-password" required maxlength="4096" ${ready?'':'disabled'}></label><button class="btn primary" type="submit" ${ready?'':'disabled'}>Sign in to workspace ${icon('arrow')}</button><p class="form-help">Workspace and role are assigned by your administrator.</p></form><button class="text-btn" data-action="retry-sign-in">Refresh sign-in</button></div></section>`;
}
async function bootstrapIdentity() {
  try {
    identityConfig = await window.contextosIdentity.configuration();
    await refresh();
  } catch(error) {
    if (identityConfig?.auth_mode === 'firebase') showSignIn(error.status===401?'':error.message);
    else {
      $('#mode').textContent = 'Workspace unavailable';
      $('#main').innerHTML = `<div class="error-panel"><h1>Workspace unavailable</h1><p>${esc(error.message)}</p>${btn('Retry','retry-sign-in',true)}</div>`;
    }
  }
}
async function action(el) {
  const a = el.dataset.action, id = el.dataset.id;
  if (a === 'retry-sign-in') return bootstrapIdentity();
  if (a === 'refresh-overview') return refresh();
  if (a === 'sign-out') {
    await window.contextosIdentity.signOut();
    showSignIn('You signed out of this browser.');
    return;
  }
  if (a === 'task-suggestion') {
    const suggestion = state.next_actions.find(x=>x.kind==='task');
    sessionStorage.setItem('task-draft',suggestion.query); go('work');
    requestAnimationFrame(()=>$('#task-query')?.focus()); return;
  }
  if (a === 'inbox-filter' && ['pending','mine','history'].includes(el.dataset.filter)) {
    inboxFilter = el.dataset.filter; render(); return;
  }
  if (['demo-next','demo-back','demo-finish'].includes(a)) {
    const report = demoReports[id];
    if (!report || demoRunning) return;
    if (a === 'demo-finish') demoCompleted[id] = true;
    else {demoPositions[id] = Math.max(0,Math.min(report.steps.length-1,(demoPositions[id]||0)+(a==='demo-next'?1:-1))); demoCompleted[id] = false;}
    render(); focusDemoStep(); return;
  }
  if (a === 'demo-persona') {demoRole = el.dataset.role; render(); return;}
  if (a === 'demo-select') {demoSelected = id; render(); return;}
  if (a === 'demo-run' || a === 'demo-all') {
    demoRunning = a === 'demo-all' ? 'all' : id;
    render();
    try {
      for (const scenarioId of (a === 'demo-all' ? demoCatalog.map(s=>s.id) : [id])) {await runDemoCase(scenarioId); render();}
    } finally {demoRunning = null; render();}
    if (a === 'demo-run') focusDemoStep();
    toast(a === 'demo-all' ? 'Verification finished. Select a case to walk through its steps.' : 'Walkthrough ready. Use Next step to continue.');
    return;
  }
  if (a === 'demo-try') {
    const scenario = demoCatalog.find(s=>s.id===id);
    await api('persona',{role:scenario.role});
    activeRun = undefined; selectedContext = undefined; queryFilter = ''; domainFilter = 'All domains'; inboxFilter = 'pending';
    sessionStorage.setItem('task-draft',scenario.query);
    await refresh(); go(scenario.view);
    if (id === 'manual' || id === 'ingestion') {addKnowledge(); if (id==='manual') await action(document.querySelector('[data-action="knowledge-mode"][data-mode="manual"]'));}
    toast(`Ready to explore as ${demoPersonas[scenario.role].title}.`);
    return;
  }
  if (a === 'navigate') {
    if (el.dataset.view === 'inbox' && ['pending','mine','history'].includes(el.dataset.filter)) inboxFilter = el.dataset.filter;
    return go(el.dataset.view);
  }
  if (a === 'close') return $('#dialog').close();
  if (a === 'context') return openContext(id);
  if (a === 'edit') return editContext();
  if (a === 'restore') {const h = selectedContext.history.find(x => x.revision === Number(el.dataset.revision)); return editContext(h.body,`Restore content from v${h.revision}; preserve all subsequent revision history.`);}
  if (a === 'manifest') return manifest(id);
  if (a === 'open-run') {activeRun = state.tasks.find(t => t.id === id); go('work'); window.scrollTo({top:0,behavior:'smooth'}); return;}
  if (a === 'ingest') return addKnowledge();
  if (a === 'knowledge-mode') {
    const manual = el.dataset.mode === 'manual';
    $('#manual-proposal-form').hidden = !manual;
    $('#ingest-form').hidden = manual;
    document.querySelectorAll('[data-action="knowledge-mode"]').forEach(button => {
      const selected = (button.dataset.mode === 'manual') === manual;
      button.setAttribute('aria-pressed', String(selected));
      button.classList.toggle('primary', selected);
    });
    return;
  }
  if (a === 'guide') return go('demo');
  if (a === 'export') {
    const data = await api('export'); const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})); const link = document.createElement('a'); link.href = url; link.download = 'contextos-evidence.json'; link.click(); URL.revokeObjectURL(url); toast('Visible workspace evidence exported.'); return;
  }
  if (a === 'approve' || a === 'reject') {const p = state.proposals.find(x => x.id === id); await api(`proposals/${id}/review`,{hash:p.hash,decision:a}); await refresh(); toast(a === 'approve' ? 'Revision published. Dependent runs checked for impact.' : 'Proposal rejected. Accepted context is unchanged.');}
  if (a === 'rerun') {const t = state.tasks.find(x => x.id === id); await runTask(t.query,t.manifest.budget);}
}
document.addEventListener('click', async e => {
  const knowledgeLink = e.target.closest('a[href="/knowledge"]');
  if (knowledgeLink && e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
    e.preventDefault(); go('knowledge'); return;
  }
  const el = e.target.closest('[data-action]'); if (!el || busy) return;
  busy = true; const wasDisabled = el.disabled; el.disabled = true;
  try {await action(el);} catch(err) {toast(err.message,true);} finally {el.disabled = wasDisabled; busy = false;}
});
document.addEventListener('submit', async e => {
  const form = e.target; if (!['task-form','proposal-form','ingest-form','manual-proposal-form','login-form'].includes(form.id)) return;
  e.preventDefault(); if (busy) return; busy = true;
  const button = form.querySelector('[type="submit"]'), previous = button.innerHTML; button.disabled = true; button.textContent = 'Working…';
  const data = Object.fromEntries(new FormData(form));
  try {
    if (form.id === 'task-form') {sessionStorage.setItem('task-draft',data.query); await runTask(data.query,Number(data.budget));}
    if (form.id === 'proposal-form') {await api('proposals',{context_id:selectedContext.id,base_revision:selectedContext.revision,body:data.body,reason:data.reason,sources:selectedContext.sources}); $('#dialog').close(); inboxFilter = 'pending'; await refresh(); go('inbox'); toast('Change proposed. The accepted revision is unchanged.');}
    if (form.id === 'manual-proposal-form') {const {source,...proposal} = data; await api('proposals',{...proposal,sources:[source]}); $('#dialog').close(); inboxFilter = 'pending'; await refresh(); go('inbox'); toast('Manual proposal created. Independent owner review is required.');}
    if (form.id === 'ingest-form') {await api('ingest',data); $('#dialog').close(); inboxFilter = 'pending'; await refresh(); go('inbox'); toast('Review candidate created.');}
    if (form.id === 'login-form') {
      form.elements.password.value = '';
      await window.contextosIdentity.signIn(data.email,data.password);
      data.password = '';
      await refresh();
    }
  } catch(err) {toast(err.message,true);} finally {busy = false; button.disabled = false; button.innerHTML = previous;}
});
$('#persona').addEventListener('change',async e => {
  if (busy) {e.target.value = state.role; return;}
  busy = true; e.target.disabled = true;
  try {await api('persona',{role:e.target.value}); activeRun = undefined; selectedContext = undefined; inboxFilter = 'pending'; $('#dialog').close(); await refresh(); toast(`Viewing as ${roleNames[state.role]}. Permissions applied.`);} catch(err) {e.target.value = state.role; toast(err.message,true);} finally {busy = false; e.target.disabled = state?.auth_mode !== 'demo';}
});
document.addEventListener('input', e => {
  if (e.target.id === 'search' && !e.isComposing) {queryFilter = e.target.value; updateKnowledgeResults();}
  if (e.target.id === 'task-query') sessionStorage.setItem('task-draft',e.target.value);
});
document.addEventListener('compositionend', e => {
  if (e.target.id === 'search') {queryFilter = e.target.value; updateKnowledgeResults();}
});
document.addEventListener('change',e => {if (e.target.id === 'demo-category') {demoCategory = e.target.value; render();} if (e.target.id === 'domain-filter') {domainFilter = e.target.value; updateKnowledgeResults();} if (e.target.id === 'task-budget') sessionStorage.setItem('task-budget',e.target.value);});
$('#dialog').addEventListener('click', e => {
  const dialog = $('#dialog');
  if (e.target !== dialog || busy) return;
  const rect = dialog.getBoundingClientRect();
  if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) return;
  const dirty = [...dialog.querySelectorAll('input,textarea,select')].some(field => field.tagName === 'SELECT' ? field.value !== [...field.options].find(o => o.defaultSelected)?.value : field.value !== field.defaultValue);
  if (dirty) {toast('Your draft is still here. Use the close button to discard it.'); return;}
  dialog.close();
});
async function routeChanged() {
  const next = viewFromUrl();
  $('#workspace-tools').open = false;
  if (next === currentView) {syncViewUrl(); return;}
  currentView = next;
  window.scrollTo({top:0,behavior:'instant'});
  if (['overview','inbox','insights'].includes(currentView) && state) {try {await refresh();} catch(error) {toast(error.message,true);}}
  else render();
}
window.addEventListener('hashchange', routeChanged);
window.addEventListener('popstate', routeChanged);
// Revalidate pages restored from the browser's back-forward cache before showing data.
window.addEventListener('pageshow', e => {
  if (e.persisted && identityConfig?.auth_mode === 'firebase') {
    clearProtectedView(); bootstrapIdentity();
  }
});
window.addEventListener('pagehide', () => {
  if (identityConfig?.auth_mode === 'firebase') clearProtectedView();
});
bootstrapIdentity();

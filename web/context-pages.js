'use strict';
window.contextPages = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const roles = ['pm','architect','developer','qa','security'];
  const button = (label, action, attrs = '', primary = false) => '<button type="button" class="btn '+(primary?'primary':'')+'" data-cp-action="'+action+'" '+attrs+'>'+label+'</button>';
  const options = (items, value, label, selected) => items.map(item=>'<option value="'+escape(value(item))+'" '+(value(item)===selected?'selected':'')+'>'+escape(label(item))+'</option>').join('');
  const badge = status => '<span class="tag '+(status==='stale'?'amber':'green')+'">'+escape(status==='up_to_date'?'Up to date':status)+'</span>';
  let root, onProposal, onUnauthorized, template, projects, project, page, parts, status, history, proposals, selectedProposal, integration={};
  let generation=0, loadVersion=0, mode='map', returnMode='map', mapView=null, mapControls=null, historical=null, showSource=false;
  const contextName = doc => {
    if(doc?.name)return doc.name;
    const label=String(doc?.filename||'Context').replace(/\.md$/i,'').replace(/[_-]+/g,' ');
    return label.charAt(0).toUpperCase()+label.slice(1);
  };
  const dateLabel = value => value && !Number.isNaN(new Date(value).getTime()) ? new Date(value).toLocaleString([], {dateStyle:'medium',timeStyle:'short'}) : '—';
  const projectPath = () => '/projects/'+encodeURIComponent(project.project.id);
  const contextPath = () => projectPath()+'/contexts/'+encodeURIComponent(page.id);
  const markdown = content => {
    if(!window.marked || !window.DOMPurify)return '<pre class="cp-markdown">'+escape(content)+'</pre>';
    return window.DOMPurify.sanitize(window.marked.parse(content), {
      ALLOWED_TAGS:['p','h1','h2','h3','h4','h5','h6','ul','ol','li','strong','em','del','code','pre','blockquote','a','hr','br','table','thead','tbody','tr','th','td'],
      ALLOWED_ATTR:['href','title'], ALLOW_DATA_ATTR:false, ALLOW_ARIA_ATTR:false
    });
  };
  async function request(path, method='GET', body) {
    const current=generation;
    const response=await fetch('/api/context'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-ContextOS-Client':'workspace'},...(body===undefined?{}:{body:JSON.stringify(body)})});
    const result=await response.json();
    if(response.status===401 && current===generation)onUnauthorized?.(result.detail||'Sign in to continue.');
    if(!response.ok)throw new Error(Array.isArray(result.detail)?result.detail.map(item=>item.msg).join('; '):result.detail||'Request failed');
    return result;
  }
  function message(text) {
    const output=root?.querySelector('#context-message');
    if(output){output.textContent=text;output.hidden=!text;}
  }
  async function load(projectId=project?.project.id, contextId=page?.id, nextMode=mode) {
    const current=generation, container=root, selection=++loadVersion;
    const active=()=>current===generation && selection===loadVersion && container?.isConnected;
    const list=await request('/projects?include_archived=true');
    if(!active())return;
    const chosen=list.find(item=>item.id===projectId)||list.find(item=>!item.archived);
    if(!chosen){projects=list;project=page=parts=status=null;history=proposals=[];mode='map';render();return;}
    const base='/projects/'+encodeURIComponent(chosen.id);
    const [nextProject,nextProposals]=await Promise.all([request(base),request(base+'/proposals')]);
    if(!active())return;
    const selected=nextProject.contexts.find(item=>item.id===contextId);
    const path=base+'/contexts/'+encodeURIComponent(selected?.id||'');
    const detail=selected?await Promise.all([request(path),request(path+'/sections'),request(path+'/status'),request(path+'/versions')]):[null,null,null,[]];
    if(!active())return;
    if(project?.project.id!==nextProject.project.id)mapView=null;
    projects=list;project=nextProject;proposals=nextProposals;[page,parts,status,history]=detail;mode=nextMode==='page'&&!selected?'map':nextMode;returnMode=selected?'page':'map';historical=null;showSource=false;selectedProposal=null;render();
    if(integration.onProjectChange && integration.projectId!==chosen.id){integration.projectId=chosen.id;await integration.onProjectChange(chosen.id);}
  }
  const panel = (title, body) => '<section class="panel"><div class="panel-head"><h2>'+escape(title)+'</h2></div><div class="panel-body">'+body+'</div></section>';
  const reasonField = '<label class="field">Reason for change<textarea name="reason" required maxlength="1500" rows="2"></textarea></label>';
  const controls = label => '<div class="button-group"><button class="btn primary" type="submit">'+label+'</button>'+button('Cancel','cancel')+'</div>';
  function projectEditor(isNew) {
    const item=isNew?{}:project.project;
    return panel(isNew?'Create project':'Edit project',
      '<form id="context-project-form" data-new="'+isNew+'"><label class="field">Project name<input name="name" required maxlength="120" value="'+escape(item.name)+'"></label>'+
      '<label class="field">Project type<input name="project_type" required maxlength="80" placeholder="Software, research, content…" value="'+escape(item.project_type)+'"></label>'+
      '<label class="field">Description<textarea name="description" maxlength="1500" rows="3">'+escape(item.description)+'</textarea></label>'+
      (isNew?'<p class="muted">You become the project admin. Creation date and time are recorded automatically. The project starts with no files.</p>':
        '<label class="field">Admin user ID<input name="admin" required maxlength="128" value="'+escape(item.admin)+'"></label><p class="muted">Created '+escape(item.created_at)+' · v'+item.version+'</p>')+
      controls(isNew?'Create empty project':'Save project')+'</form>');
  }
  function contextEditor(isNew) {
    const item=isNew?{content:template.content,relationships:[],owner:'',owner_type:'pm'}:page;
    const links=project.contexts.filter(doc=>doc.id!==item.id);
    return panel(isNew?'Propose new context':'Propose context update',
      '<form id="context-page-form" data-new="'+isNew+'"><label class="field">Context name<input name="name" required maxlength="120" placeholder="System Architecture" value="'+escape(isNew?'':contextName(item))+'"></label><div class="cp-fields"><label class="field">File name<input name="filename" required maxlength="100" placeholder="architecture.md" value="'+escape(item.filename)+'"></label>'+
      '<label class="field">Owner<input name="owner" required maxlength="128" placeholder="Person or team" value="'+escape(item.owner)+'"></label>'+
      '<label class="field">Owner type<select name="owner_type" aria-label="Owner type">'+options(roles,value=>value,value=>value,item.owner_type)+'</select></label></div>'+
      '<label class="field">Markdown content<textarea name="content" aria-label="Markdown content" rows="17" maxlength="10000" required>'+escape(item.content)+'</textarea></label>'+
      '<p class="muted">Keep the three section headings: Overview, Details and Next steps. Use ### for subheadings. Approved requirements and security pages are required sources for every task in this project.</p>'+
      '<fieldset class="cp-relationships"><legend>Relationships</legend>'+(links.map(doc=>{
        const kind=item.relationships.find(link=>link.target_id===doc.id)?.kind||'';
        return '<label class="field">'+escape(contextName(doc))+'<select name="link:'+escape(doc.id)+'">'+options(['','depends_on','references'],value=>value,value=>value===''?'No relationship':value==='depends_on'?'Depends on':'References',kind)+'</select></label>';
      }).join('')||'<p class="muted">Approve another context first to connect it.</p>')+'</fieldset>'+
      reasonField+'<p class="muted">An independent '+escape(isNew?'designated owner-role':page.owner_type)+' reviewer must approve publication. An owner-type transfer is reviewed by the current owner role.</p>'+controls('Submit proposal')+'</form>');
  }
  function pageList(items) {
    return items.map(item=>'<button type="button" class="context-row cp-context-row '+(page?.id===item.id?'cp-active':'')+'" data-cp-action="select" data-id="'+escape(item.id)+'" aria-pressed="'+(page?.id===item.id)+'"><span class="row-main"><strong>'+escape(contextName(item))+'</strong><small>'+escape(item.status==='up_to_date'?'Up to date':item.status)+' · v'+item.version+'</small></span><span class="cp-open-arrow" aria-hidden="true">↗</span></button>').join('')||'<p class="muted cp-list-empty">No matching contexts.</p>';
  }
  function pageView() {
    const doc=historical||page;
    if(!doc)return mapViewMarkup();
    return '<article class="panel cp-reader"><header class="cp-reader-header"><p class="cp-kicker">'+(historical?'Historical context · version '+doc.version:'Context')+'</p><h2 id="context-reader-title" tabindex="-1">'+escape(contextName(doc))+'</h2><div class="cp-reader-tabs" role="group" aria-label="Content format">'+
      button('Read','read','aria-pressed="'+!showSource+'"')+button('Markdown','source','aria-pressed="'+showSource+'"')+'</div></header>'+
      '<div class="cp-reader-body">'+(showSource?'<pre class="cp-markdown cp-source">'+escape(doc.content)+'</pre>':'<div class="cp-rendered">'+markdown(doc.content)+'</div>')+'</div></article>';
  }
  function relationshipsView(doc) {
    const outgoing=doc.relationships||[], incoming=project.relationships.filter(link=>link.target_id===doc.id);
    const row=(link,inbound)=>{
      const id=inbound?link.source_id:link.target_id, target=project.contexts.find(item=>item.id===id);
      return '<li><span>'+escape(inbound?(link.kind==='depends_on'?'Used by':'Referenced by'):(link.kind==='depends_on'?'Depends on':'References'))+'</span>'+button(escape(contextName(target||{name:id})),'select','data-id="'+escape(id)+'"')+'</li>';
    };
    return '<ul class="cp-related">'+(outgoing.map(link=>row(link,false)).join('')+incoming.map(link=>row(link,true)).join('')||'<li class="muted">No relationships yet.</li>')+'</ul>';
  }
  function contextMetadata() {
    const doc=historical||page;
    return '<section class="cp-side-section"><h3>Context details</h3><div class="cp-status-row">'+(historical?'<span class="tag">Historical · v'+doc.version+'</span>':badge(status.status)+'<span class="tag">Approved · v'+page.version+'</span>')+'</div>'+
      (!historical&&status.pending_proposals?'<p class="cp-meta-note">'+status.pending_proposals+' pending proposal'+(status.pending_proposals===1?'':'s')+'</p>':'')+
      (!historical&&status.status==='stale'?'<p class="note amber">A dependency changed. Review and propose an update to refresh this context.</p>':'')+
      '<dl class="cp-metadata"><div><dt>Owner</dt><dd>'+escape(doc.owner)+'</dd></div><div><dt>Owner type</dt><dd>'+escape(doc.owner_type)+'</dd></div><div><dt>Updated</dt><dd>'+escape(dateLabel(doc.updated_at))+'</dd></div><div><dt>File</dt><dd>'+escape(doc.filename)+'</dd></div></dl>'+
      (historical?button('Return to current version','current'):!project.project.archived?button('Propose edit','edit','',true):'')+'</section>'+
      '<section class="cp-side-section"><h3>Relationships</h3>'+relationshipsView(doc)+'</section>'+
      '<details class="cp-side-section"><summary>Version history <span>'+history.length+'</span></summary><div class="cp-version-list">'+history.map(item=>'<div>'+button('Version '+item.version,'version','data-version="'+item.version+'"')+'<p>'+escape(item.reason)+'</p><small>'+escape(item.approved_by)+'</small></div>').join('')+'</div></details>'+
      (!historical?'<details class="cp-side-section"><summary>Extract content</summary><form id="context-extract-form" class="cp-side-form"><label class="field">Section<select name="section_key"><option value="">All sections</option>'+options(parts.sections,item=>item.key,item=>item.heading)+'</select></label><label class="field">Containing text<input name="query" maxlength="500"></label><button type="submit" class="btn">Extract</button><pre id="context-extract-result" class="cp-markdown" hidden></pre></form></details>':'')+
      '<details class="cp-side-section"><summary>More actions</summary><div class="cp-side-actions">'+button('Download .md','download')+(!historical&&!project.project.archived?button('Propose deletion','delete'):'')+'</div></details>';
  }
  function projectMetadata() {
    const item=project.project;
    return '<section class="cp-side-section"><h3>Project details</h3><p class="cp-project-description">'+escape(item.description||'No project description yet.')+'</p><dl class="cp-metadata"><div><dt>Type</dt><dd>'+escape(item.project_type)+'</dd></div><div><dt>Admin</dt><dd>'+escape(item.admin)+'</dd></div><div><dt>Created</dt><dd>'+escape(dateLabel(item.created_at))+'</dd></div></dl>'+ (item.archived?badge('archived'):'')+button('Edit project details','project-details')+'</section>';
  }
  function contextCatalog(collapsed) {
    const content='<form id="context-search-form" class="cp-side-form"><label class="field">Find context<input name="query" type="search" placeholder="Search contexts…" maxlength="500"></label><button class="btn small" type="submit">Search</button></form><div class="cp-context-list" id="context-page-list">'+pageList(project.contexts)+'</div>';
    return collapsed?'<details class="cp-side-section"><summary>Other contexts <span>'+project.contexts.length+'</span></summary>'+content+'</details>':'<section class="cp-side-section"><h3>Contexts <span>'+project.contexts.length+'</span></h3>'+content+'</section>';
  }
  function inspector() {
    const reading=page&&['page','version','context-edit','delete'].includes(mode);
    return '<aside class="panel cp-inspector" aria-label="'+(reading?'Context metadata':'Project metadata')+'">'+(reading?contextMetadata():projectMetadata())+
      '<section class="cp-side-section cp-side-actions"><h3>Manage knowledge</h3>'+(!project.project.archived?button('New context','new','',!reading):'')+button('Proposals ('+proposals.filter(item=>item.status==='pending').length+')','reviews')+button('New project','project-new')+'</section>'+contextCatalog(!!reading)+'</aside>';
  }
  function mapViewMarkup() {
    if(!project.contexts.length)return '<section class="panel cp-empty-map"><div class="cp-empty-symbol" aria-hidden="true">◇</div><h2>Your knowledge map starts here</h2><p>Propose a context, then connect it to other approved knowledge.</p>'+(!project.project.archived?button('New context','new','',true):'')+'</section>';
    return '<div class="cp-canvas">'+window.contextMap.render(project.contexts.map(item=>({...item,title:contextName(item),domain:item.owner_type+(item.status==='stale'?' · stale':''),revision:item.version})),project.relationships,page?.id,mapView?.zoom??1)+'</div>';
  }
  function proposalList() {
    return panel('Project proposals', proposals.map(item=>'<button type="button" class="context-row" data-cp-action="proposal" data-id="'+escape(item.id)+'"><span class="row-main"><strong>'+escape(item.action)+' · '+escape(contextName(item))+'</strong><small>'+escape(item.status)+' · '+escape(item.author)+' → '+escape(item.reviewer_type)+' reviewer</small><small>'+escape(item.reason)+'</small></span></button>').join('')||'<p>No proposals yet.</p>');
  }
  function candidateView(item) {
    return '<p><strong>'+escape(contextName(item))+'</strong> · '+escape(item.owner)+' · '+escape(item.owner_type)+'</p><p class="muted">File: '+escape(item.filename)+'</p><p class="muted">Relationships: '+escape(item.relationships.map(link=>contextName(project.contexts.find(doc=>doc.id===link.target_id)||{name:link.target_id})+' ('+link.kind+')').join(', ')||'None')+'</p><article class="cp-rendered">'+markdown(item.content)+'</article><details><summary>Exact Markdown source</summary><pre class="cp-markdown">'+escape(item.content)+'</pre></details>';
  }
  function proposalView() {
    const item=selectedProposal,canReview=item.status==='pending' && project.actor!==item.author && project.role===item.reviewer_type;
    return panel(item.action==='delete'?'Review context deletion':'Review proposed context',
      '<p>'+badge(item.status)+' · '+escape(item.author)+' · '+escape(item.reason)+'</p>'+
      '<p class="muted">Required reviewer: '+escape(item.reviewer_type)+' · Base version '+item.base_version+'</p>'+
      (item.action==='delete'?'<p class="note amber">Approval removes this context from the active project. Historical versions are retained.</p>':'')+
      (item.before?'<details><summary>Accepted version '+item.base_version+'</summary>'+candidateView(item.before)+'</details>':'')+
      '<h3>Proposed '+(item.action==='delete'?'deletion':'version')+'</h3>'+candidateView(item.candidate)+
      (canReview?'<div class="button-group">'+button('Approve','approve','',true)+button('Reject','reject')+'</div>':
      item.status==='pending'?'<p class="note amber">An independent '+escape(item.reviewer_type)+' reviewer must decide this change. In demo mode, use the persona selector to switch to that reviewer.</p>':'')+
      button('All proposals','reviews'));
  }
  function detail() {
    if(mode==='project-new'||mode==='project-edit')return projectEditor(mode==='project-new');
    if(mode==='context-new'||mode==='context-edit')return contextEditor(mode==='context-new');
    if(mode==='reviews')return proposalList();
    if(mode==='proposal')return proposalView();
    if(mode==='delete'||mode==='archive')return panel(mode==='delete'?'Propose context deletion':'Archive project',
      '<form id="context-delete-form" data-kind="'+mode+'"><p>'+escape(mode==='delete'?contextName(page):project.project.name)+'</p><p class="muted">'+(mode==='delete'?'Deletion requires owner-role approval.':'Archiving hides the project from active lists. You can restore it; history is retained.')+'</p>'+reasonField+controls(mode==='delete'?'Submit deletion proposal':'Archive project')+'</form>');
    if(mode==='map')return mapViewMarkup();
    return pageView();
  }
  function render() {
    mapControls?.destroy();mapControls=null;
    const focused=root.querySelector('[data-cp-map-node]:focus');
    const focusId=focused?.dataset.id, meta=project?.project;
    const toolbar='<div class="cp-toolbar">'+(projects.length?'<label class="cp-project-picker">Project<select id="context-project-select" aria-label="Project">'+(!meta?'<option value="" selected disabled>Select a project</option>':'')+options(projects,item=>item.id,item=>item.name+(item.archived?' (archived)':''),meta?.id)+'</select></label>':'')+
      (meta?(mode!=='map'?button('← Back to map','map'):'<p class="cp-workspace-counts">'+project.contexts.length+' contexts · '+project.relationships.length+' relationships</p>'):button('New project','project-new'))+'</div>';
    root.innerHTML='<div id="context-message" class="note amber" role="status" hidden></div>'+toolbar+
      (meta?'<div class="cp-workspace '+(mode==='map'?'cp-map-layout':'cp-reading-layout')+'"><section id="context-detail" class="cp-primary" tabindex="-1" aria-label="'+(mode==='map'?'Knowledge visualization':'Context workspace')+'">'+detail()+'</section>'+inspector()+'</div>':
      '<div id="context-detail" class="cp-primary" tabindex="-1">'+(mode==='project-new'?projectEditor(true):panel('Create your first project','<p>Start with a project name, type and description. Add contexts when you are ready.</p>'+button('Create project','project-new','',true)))+'</div>');
    if(mode==='map'){
      mapControls=window.contextMap.mount(root,mapView,view=>{mapView=view;});
      if(focusId)[...root.querySelectorAll('[data-cp-map-node]')].find(card=>card.dataset.id===focusId)?.focus({preventScroll:true});
    }
  }
  function focusPrimary(selector='#context-detail') {
    root?.querySelector(selector)?.focus({preventScroll:true});
    root?.querySelector('.cp-toolbar')?.scrollIntoView({block:'start',behavior:'smooth'});
  }
  function showMode(next) {
    loadVersion++;
    if(mode==='map'||mode==='page'||mode==='version')returnMode=mode==='map'?'map':'page';
    historical=null;showSource=false;mode=next;render();focusPrimary();
  }
  async function action(target) {
    const action=target.dataset.cpAction,current=generation;
    if(action.startsWith('map-'))return mapControls?.command(action);
    if(action==='select'){
      const id=target.dataset.id;
      await load(project.project.id,id,'page');
      if(current===generation&&page?.id===id&&mode==='page')focusPrimary('#context-reader-title');
      return;
    }
    if(action==='map'){showMode('map');root?.querySelector('.cp-map-viewport')?.focus({preventScroll:true});return;}
    if(action==='read'||action==='source'){showSource=action==='source';render();root?.querySelector('[data-cp-action="'+action+'"]')?.focus({preventScroll:true});return;}
    if(action==='current'){loadVersion++;historical=null;mode='page';render();focusPrimary('#context-reader-title');return;}
    if(action==='project-new'){showMode('project-new');return;}
    if(action==='new'||action==='edit'){showMode(action==='new'?'context-new':'context-edit');return;}
    if(action==='cancel'){showMode(returnMode);return;}
    if(action==='reviews'){showMode('reviews');return;}
    if(action==='delete'){showMode('delete');return;}
    if(action==='project-details'){
      showMode('project-edit');
      if(project.actor!==project.project.admin){
        root.querySelector('#context-project-form').querySelectorAll('input,textarea,button[type="submit"]').forEach(input=>input.disabled=true);
        message('Only '+project.project.admin+' can edit project metadata.');
      } else {
        root.querySelector('#context-project-form').insertAdjacentHTML('beforeend',button(project.project.archived?'Restore project':'Archive project',project.project.archived?'restore':'archive'));
      }
      return;
    }
    if(action==='archive'){showMode('archive');return;}
    if(action==='restore'){
      const item=project.project;
      await request(projectPath(),'PUT',{name:item.name,project_type:item.project_type,description:item.description,admin:item.admin,expected_version:item.version,archived:false});
      if(current===generation)await load();
      return;
    }
    if(action==='proposal'){
      const ticket=++loadVersion;
      const result=await request(projectPath()+'/proposals/'+encodeURIComponent(target.dataset.id));
      if(current!==generation||ticket!==loadVersion||!root?.isConnected)return;
      selectedProposal=result;showMode('proposal');return;
    }
    if(action==='approve'||action==='reject'){
      target.disabled=true;
      try{
        await request(projectPath()+'/proposals/'+encodeURIComponent(selectedProposal.id)+'/review','POST',{hash:selectedProposal.hash,decision:action==='approve'?'approve':'reject'});
        if(current===generation){await load(project.project.id,selectedProposal.context_id,action==='approve'?'page':'reviews');message(action==='approve'?'Proposal approved.':'Proposal rejected.');}
        if(current===generation)await integration.onChanged?.();
      }finally{target.disabled=false;}
      return;
    }
    if(action==='version'){
      const ticket=++loadVersion;
      const result=await request(contextPath()+'/versions/'+encodeURIComponent(target.dataset.version));
      if(current===generation&&ticket===loadVersion&&root?.isConnected){historical=result;mode='version';showSource=false;render();focusPrimary('#context-reader-title');}
      return;
    }
    if(action==='download'){
      const doc=historical||page,blob=new Blob([doc.content],{type:'text/markdown;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=doc.filename;link.click();URL.revokeObjectURL(url);
    }
  }
  async function submit(form) {
    const current=generation,selection=loadVersion,input=Object.fromEntries(new FormData(form));
    const active=()=>current===generation && selection===loadVersion && root?.isConnected;
    if(form.id==='context-project-form'){
      const isNew=form.dataset.new==='true';
      const data={name:input.name,project_type:input.project_type,description:input.description};
      if(!isNew)Object.assign(data,{admin:input.admin,expected_version:project.project.version,archived:project.project.archived});
      const result=await request(isNew?'/projects':projectPath(),isNew?'POST':'PUT',data);
      if(active())await load(result.id,null,'map');
    }
    if(form.id==='context-page-form'){
      const isNew=form.dataset.new==='true';
      const data={name:input.name,filename:input.filename,content:input.content,owner:input.owner,owner_type:input.owner_type,reason:input.reason,relationships:Object.entries(input).filter(([key,value])=>key.startsWith('link:')&&value).map(([key,kind])=>({target_id:key.slice(5),kind}))};
      if(!isNew)data.expected_version=page.version;
      await request(isNew?projectPath()+'/contexts':contextPath(),isNew?'POST':'PUT',data);
      if(active()){await load(project.project.id,page?.id,'reviews');await onProposal?.();}
    }
    if(form.id==='context-delete-form'){
      await request(form.dataset.kind==='archive'?projectPath():contextPath(),'DELETE',{expected_version:form.dataset.kind==='archive'?project.project.version:page.version,reason:input.reason});
      if(active())await load(project.project.id,page?.id,form.dataset.kind==='archive'?'map':'reviews');
    }
    if(form.id==='context-search-form'){
      const result=await request(projectPath()+'/search?q='+encodeURIComponent(input.query));
      if(active())root.querySelector('#context-page-list').innerHTML=pageList(result.items);
    }
    if(form.id==='context-extract-form'){
      const result=await request(contextPath()+'/extract','POST',{section_keys:input.section_key?[input.section_key]:[],query:input.query,max_chars:8000});
      if(!active())return;
      const output=root.querySelector('#context-extract-result');
      output.textContent='Approved version '+result.version+'\n\n'+(result.content||'No matching content.');output.hidden=false;
    }
  }
  async function run(operation) {const current=generation;try{message('');await operation();}catch(error){if(current===generation)message(error.message);}}
  function clear() {
    mapControls?.destroy();mapControls=null;
    generation++;loadVersion++;mapView=null;historical=null;showSource=false;mode=returnMode='map';
    root=onProposal=onUnauthorized=template=projects=project=page=parts=status=history=proposals=selectedProposal=null;
    integration={};
  }
  async function mount(element, afterProposal, onExpired, options={}) {
    clear();const current=generation;root=element;onProposal=afterProposal;onUnauthorized=onExpired;
    integration={...options};
    root.addEventListener('click',event=>{const target=event.target.closest('[data-cp-action]');if(target)run(()=>action(target));});
    root.addEventListener('change',event=>{if(event.target.id==='context-project-select')run(()=>load(event.target.value,null,'map'));});
    root.addEventListener('submit',event=>{
      event.preventDefault();const submitButton=event.target.querySelector('[type="submit"]');
      if(submitButton?.disabled)return;if(submitButton)submitButton.disabled=true;
      run(()=>submit(event.target)).finally(()=>{if(submitButton)submitButton.disabled=false;});
    });
    root.addEventListener('keydown',event=>{
      if(!event.target.matches('[data-cp-map-node]'))return;
      if(event.key==='Enter'||event.key===' '){event.preventDefault();run(()=>action(event.target));return;}
      const direction={ArrowRight:[1,0],ArrowLeft:[-1,0],ArrowDown:[0,1],ArrowUp:[0,-1]}[event.key];
      if(!direction)return;
      event.preventDefault();
      const distance=card=>{const x=Number(card.dataset.mapX)-Number(event.target.dataset.mapX),y=Number(card.dataset.mapY)-Number(event.target.dataset.mapY);const forward=x*direction[0]+y*direction[1];return forward>0?forward+3*Math.abs(x*direction[1]-y*direction[0]):Infinity;};
      [...root.querySelectorAll('[data-cp-map-node]')].filter(card=>Number.isFinite(distance(card))).sort((a,b)=>distance(a)-distance(b))[0]?.focus();
    });
    try{
      const result=await request('/template');
      if(current!==generation||!element.isConnected)return;
      template=result;await load(integration.projectId);
    }catch(error){if(current===generation&&element.isConnected)element.textContent=error.message;}
  }
  return {mount,clear};
})();

'use strict';
// Own request keys and pending recovery independently of the workspace renderer.
window.taskConversations = {
  create({request, onUpdate, onError, newId = () => crypto.randomUUID()}) {
    let current=null, pending=null, creation=null, generation=0, timer=null, polls=0;
    const clear = () => {generation++;clearTimeout(timer);current=pending=creation=null;polls=0;};
    const notify = () => onUpdate?.(current,pending);
    const unfinished = () => current?.turns?.at(-1)?.status === 'pending';
    async function reload(version=generation) {
      if(!current)return;
      let result;
      try {result=await request('conversations/'+encodeURIComponent(current.id));}
      catch(error){
        if(version===generation && [401,403,404].includes(error.status)){clear();notify();}
        throw error;
      }
      if(version!==generation)return;
      current=result;
      if(pending && current.turns.some(t=>t.request_id===pending.request_id && t.status==='succeeded'))pending=null;
      notify();
      clearTimeout(timer);
      if(unfinished() && polls++<30)timer=setTimeout(()=>reload(version).catch(error=>{
        if(version===generation)onError?.(error);
      }),1500);
    }
    async function open(id) {
      clear();const version=generation;
      const result=await request('conversations/'+encodeURIComponent(id));
      if(version!==generation)return;
      current=result;notify();
      if(unfinished())await reload(version);
    }
    async function send(query,budget,refresh_context=false,project_id=null) {
      const version=generation;
      const previous=current?.turns?.at(-1);
      if(!pending && previous && previous.status!=='succeeded'){
        pending={query:previous.query,budget:previous.manifest.budget,
          request_id:previous.request_id,refresh_context:previous.refresh_context};
      }
      if(pending && (pending.query!==query || pending.budget!==budget || pending.refresh_context!==refresh_context))
        throw new Error('Retry the unfinished message before sending a different follow-up.');
      pending ||= {query,budget,refresh_context,request_id:newId()};
      polls=0;
      try {
        if(!current){
          creation ||= {title:query.slice(0,120),request_id:newId(),project_id};
          const result=await request('conversations',creation);
          if(version!==generation)return;
          current={...result,turns:[]};notify();
        }
        await request('conversations/'+encodeURIComponent(current.id)+'/turns',pending);
      } finally {
        if(version===generation && current)await reload(version);
      }
    }
    async function retry() {
      const previous=current?.turns?.at(-1);
      const input=pending || (previous && {query:previous.query,budget:previous.manifest.budget,
        refresh_context:previous.refresh_context,request_id:previous.request_id});
      if(!input)throw new Error('There is no unfinished message to retry.');
      pending=input;
      return send(input.query,input.budget,input.refresh_context,creation?.project_id || current?.project_id || null);
    }
    return {clear,open,send,retry,reload,
      get current(){return current;},get pending(){return pending;}};
  }
};

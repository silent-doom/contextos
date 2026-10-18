const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function controller(request) {
  const updates=[],errors=[],timers=new Map();let sequence=0;
  const runtime=vm.createContext({window:{},setTimeout:fn=>{timers.set(++sequence,fn);return sequence;},clearTimeout:id=>timers.delete(id)});
  vm.runInContext(fs.readFileSync('web/conversations.js','utf8'),runtime);
  const chat=runtime.window.taskConversations.create({request,onUpdate:item=>updates.push(item),onError:error=>errors.push(error),newId:()=>`request-${++sequence}`});
  return {chat,updates,errors,timers};
}
function saved(turns=[]) {return {id:'CHAT-1',project_id:'PRJ-1',title:'Payment retries',turns};}
function turn(input,status='succeeded') {return {...input,id:'RUN-1',status,manifest:{budget:input.budget},output:'Accepted briefing'};}

test('messages and follow-ups stay in one private project conversation with distinct request keys',async()=>{
  const calls=[],record=saved();
  const {chat}=controller(async(path,body)=>{
    calls.push({path,body});
    if(path==='conversations')return {...record,turn_ids:[]};
    if(body){record.turns.push(turn(body));return record.turns.at(-1);}
    return structuredClone(record);
  });
  await chat.send('Implement payment retries',6000,false,'PRJ-1');
  await chat.send('What tests should I add?',6000,false,'PRJ-1');
  assert.equal(calls.filter(c=>c.path==='conversations').length,1);
  assert.equal(calls[0].body.project_id,'PRJ-1');
  assert.equal(chat.current.turns.length,2);
  assert.notEqual(record.turns[0].request_id,record.turns[1].request_id);
  assert.equal(chat.pending,null);
});

test('failed replies retain the exact input and request key when retried',async()=>{
  const record=saved(),inputs=[];let failing=true;
  const {chat}=controller(async(path,body)=>{
    if(path==='conversations')return record;
    if(!body)return structuredClone(record);
    inputs.push(structuredClone(body));record.turns=[turn(body,failing?'failed':'succeeded')];
    if(failing)throw new Error('Provider unavailable');
    return record.turns[0];
  });
  await assert.rejects(chat.send('Implement retries',3000,true,'PRJ-1'),/Provider/);
  await assert.rejects(chat.send('Different task',3000,true,'PRJ-1'),/Retry the unfinished/);
  failing=false;await chat.retry();
  assert.deepEqual(inputs[0],inputs[1]);
  assert.equal(chat.current.turns.length,1);
  assert.equal(chat.pending,null);
});

test('reopening an unfinished turn retries its server request key and never creates another chat',async()=>{
  const original={query:'Implement retries',budget:6000,refresh_context:false,request_id:'original-message-key'};
  const record=saved([turn(original,'failed')]),calls=[];
  const {chat}=controller(async(path,body)=>{
    calls.push({path,body});
    if(body){record.turns=[turn(body)];return record.turns[0];}
    return structuredClone(record);
  });
  await chat.open('CHAT-1');await chat.retry();
  const sent=calls.find(c=>c.body).body;
  assert.deepEqual(JSON.parse(JSON.stringify(sent)),original);
  assert.equal(calls.some(c=>c.path==='conversations'),false);
});

test('pending replies are read through polling without repeating the model request',async()=>{
  const input={query:'Payment retry tests',budget:6000,refresh_context:false,request_id:'pending-request'};
  const record=saved([turn(input,'pending')]);let writes=0;
  const {chat,timers}=controller(async(path,body)=>{if(body)writes++;return structuredClone(record);});
  await chat.open('CHAT-1');assert.equal(timers.size,1);
  record.turns[0].status='succeeded';
  await [...timers.values()][0]();
  assert.equal(chat.current.turns[0].status,'succeeded');assert.equal(writes,0);
  chat.clear();assert.equal(timers.size,0);
});

for(const phase of ['creation','reply'])test(`cleanup discards a late ${phase} result and cancels recovery`,async()=>{
  let deliver;
  const record=saved();
  const {chat,timers}=controller(async(path,body)=>{
    if((phase==='creation'&&path==='conversations')||(phase==='reply'&&path.endsWith('/turns')))
      return new Promise(resolve=>deliver=resolve);
    if(path==='conversations')return record;
    return record;
  });
  const pending=chat.send('Private work',6000,false,'PRJ-1');
  await new Promise(resolve=>setImmediate(resolve));
  chat.clear();deliver(record);await pending;
  assert.equal(chat.current,null);assert.equal(chat.pending,null);assert.equal(timers.size,0);
});

test('lost conversation access clears private messages and pending polling',async()=>{
  let revoked=false;
  const {chat,updates,timers}=controller(async()=>{
    if(revoked)throw Object.assign(new Error('Unavailable'),{status:404});
    return saved([turn({query:'Private work',budget:6000})]);
  });
  await chat.open('CHAT-1');revoked=true;
  await assert.rejects(chat.reload(),/Unavailable/);
  assert.equal(chat.current,null);assert.equal(updates.at(-1),null);assert.equal(timers.size,0);
});

test('uncertain conversation creation can be retried with its original creation and message keys',async()=>{
  let fail=true;const keys=[],record=saved();
  const {chat}=controller(async(path,body)=>{
    if(path==='conversations'){keys.push(body.request_id);if(fail)throw new Error('Network lost');return record;}
    if(body){record.turns=[turn(body)];return record.turns[0];}
    return structuredClone(record);
  });
  await assert.rejects(chat.send('Implement retries',6000,false,'PRJ-1'),/Network/);
  fail=false;await chat.retry();
  assert.equal(keys[0],keys[1]);assert.equal(chat.current.turns.length,1);
});

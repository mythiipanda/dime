import assert from "node:assert/strict";
import {test} from "node:test";
import {createServer} from "node:http";
import {existsSync,readFileSync} from "node:fs";
import {mkdir,readdir,writeFile,mkdtemp,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {createPiExecution as createPiExec} from "./dist/pi-execution.js";
import {createAnalyst,threadWorkspacePath} from "./dist/analyst.js";
import {ProductStore} from "./dist/product-store.js";

const root=process.env.DIME_PI_TEST_ROOT;
assert(root,"Owned fixture directory required");
const requests=[];
let scenario="normal";
let entered;
const server=createServer(async(req,res)=>{
  let body="";
  for await(const chunk of req) body+=chunk;
  const request=JSON.parse(body);
  requests.push(request);
  res.writeHead(200,{"content-type":"text/event-stream"});
  if(scenario === "abort") {res.write(": waiting\n\n");entered();return;}
  const toolResult=request.messages.some(m=>m.role === "tool");
  const chunk=delta=>res.write("data: "+JSON.stringify({id:"fixture",object:"chat.completion.chunk",created:1,model:"fixture",choices:[{index:0,delta,finish_reason:null}]})+"\n\n");
  if(!toolResult) {
    const code=scenario === "followup"
      ? `let denied=false; try { await tools.read_source({ref:"unowned"}); } catch {denied=true;} const source=await tools.read_source({ref:${JSON.stringify(globalThis.priorRef)}}); const carry=load("carry_marker"); return {denied,carryTeam:carry && carry.team,secretPresent:source.result.rows[1]._source.length === 14,pts:source.result.rows[0].PTS};`
      : `let denied=false; try {await tools.watchlist_add({});} catch {denied=true;} const bad=await tools.sql_exec({sql:"SELECT missing FROM silver_leaders_pts"}); const source=await tools.sql_exec({sql:"SELECT PTS, _source FROM silver_hist_player_seasons ORDER BY PTS"}); store("carry_marker",{team:"carry-BOS-marker",season:"2025-26"}); return {denied,failed:bad.isError,ref:source.ref,pts:source.result.rows[0].PTS,unit:source.result.declared_column_semantics.PTS.unit};`;
    chunk({role:"assistant",tool_calls:[{index:0,id:"call-fixture",type:"function",function:{name:"codemode",arguments:JSON.stringify({code})}}]});
  } else chunk({role:"assistant",content:"Synthetic answer"});
  res.write("data: "+JSON.stringify({id:"fixture",object:"chat.completion.chunk",created:1,model:"fixture",choices:[{index:0,delta:{},finish_reason:toolResult?"stop":"tool_calls"}]})+"\n\ndata: [DONE]\n\n");
  res.end();
});

test("in-process Pi + QuickJS + Python MCP over local OpenAI SSE, source reuse and abort",async()=>{
  server.listen(0,"127.0.0.1");
  await new Promise(resolve=>server.once("listening",resolve));
  const address=server.address();
  assert(address && typeof address !== "string");
  const cwd=join(root,"inprocess");
  await mkdir(join(cwd,"agent"),{recursive:true});
  const env=Object.fromEntries(["SystemRoot","WINDIR","PATH","LANG"].filter(k=>process.env[k]).map(k=>[k,process.env[k]]));
  Object.assign(env,{HOME:cwd,USERPROFILE:cwd,TEMP:cwd,TMP:cwd,OPENBLAS_NUM_THREADS:"1",OMP_NUM_THREADS:"1",POLARS_MAX_THREADS:"1",DIME_WAREHOUSE:process.env.DIME_WAREHOUSE});
  const context={q:"fixture question",history:[],sources:[],cwd,agentDir:join(cwd,"agent"),
    model:{provider:"fixture",model:"fixture",baseUrl:`http://127.0.0.1:${address.port}/v1`,apiKey:"synthetic",contextWindow:100000,maxTokens:4000},
    bridge:{python:process.env.DIME_PI_PYTHON,cwd,env}};
  const analyst=createPiExec();
  try {
    const events=[];
    for await(const event of analyst.stream(context)) events.push(event);
    assert(!events.some(e=>e.type === "failure"),JSON.stringify(events));
    assert.equal(events.find(e=>e.type === "answer")?.text,"Synthetic answer");
    const statuses=events.filter(e=>e.type === "status").map(e=>e.text);
    assert.equal(statuses[0],"Reading the question");
    assert(statuses.slice(1).every(text=>text === "Weighing the evidence"),JSON.stringify(statuses));
    const kindOrder=events.map(e=>e.type);
    assert(kindOrder.indexOf("status")<kindOrder.indexOf("answer"),JSON.stringify(kindOrder));
    const sources=events.filter(e=>e.type === "source").map(e=>e.record);
    assert.equal(sources.length,2);
    assert.equal(JSON.parse(sources[0].response.content[0].text).ok,false);
    assert(JSON.stringify(sources).includes("RAW_SECRET_ROW"));
    assert(!JSON.stringify(requests).includes("RAW_SECRET_ROW"));
    assert(JSON.stringify(requests).includes('denied'));
    assert(requests.some(r=>r.messages.some(m=>m.role === 'tool' && m.content.includes('true'))));
    const pid=events.find(e=>e.type === "closed").pid;
    assert(pid);
    assert.throws(()=>process.kill(pid,0));
    await writeFile(join(root,"inprocess-sources.json"),JSON.stringify(sources));
    scenario="followup";globalThis.priorRef=sources[1].ref;
    const followup=[];
    for await(const event of analyst.stream({...context,sources,history:[{role:"user",content:"prior question"},{role:"assistant",content:"prior answer"}]})) followup.push(event);
    assert.equal(followup.find(e=>e.type === "answer")?.text,"Synthetic answer");
    assert(!followup.some(e=>e.type === "source"));
    assert(!JSON.stringify(requests).includes("RAW_SECRET_ROW"));
    assert(JSON.stringify(requests).includes('secretPresent'));
    assert(JSON.stringify(requests).includes('carry-BOS-marker'));
    assert(existsSync(join(cwd,"codemode-store.json")));
    scenario="abort";
    const controller=new AbortController();
    const ready=new Promise(resolve=>{entered=resolve;});
    const aborted=[];
    const pending=(async()=>{for await(const event of analyst.stream(context,controller.signal)) aborted.push(event);})();
    await ready;controller.abort();await pending;
    assert(!aborted.some(e=>e.type === "answer"));
    const abortedPid=aborted.find(e=>e.type === "closed").pid;
    assert(abortedPid);assert.throws(()=>process.kill(abortedPid,0));
    const invalid=[];
    for await(const event of analyst.stream({...context,model:{}})) invalid.push(event);
    assert.equal(invalid[0].type,"failure");assert.equal(invalid[0].kind,"configuration");
  } finally {server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test("createAnalyst retains persistent per-thread workspace across turns and cleans ephemeral dirs",async()=>{
  const privateDir=join(root,"analyst-ws-private");
  const dbPath=join(root,"analyst-ws-conv.sqlite");
  const sourcesDir=join(root,"analyst-ws-sources");
  const seenBridgeEnvs=[];
  const seenHistories=[];
  const mockExec={
    async *stream(ctx){
      seenBridgeEnvs.push({cwd:ctx.bridge.cwd,ws:ctx.bridge.env.DIME_THREAD_WORKSPACE,timeout:ctx.runTimeoutMs});
      seenHistories.push(ctx.history);
      await writeFile(join(ctx.bridge.cwd,"turn-artifact.txt"),"persisted-data","utf8");
      yield {type:"answer",text:"Turn complete",reasoning:"Turn reasoning"};
      yield {type:"closed"};
    }
  };
  const analyst=createAnalyst({
    env:{...process.env,DIME_PI_PRIVATE_DIR:privateDir,DIME_CONVERSATION_STORE:dbPath,DIME_PI_SOURCES_DIR:sourcesDir,DIME_WAREHOUSE:process.env.DIME_WAREHOUSE},
    resolveModel:()=>({id:"fixture",name:"Fixture",provider:"fixture",api:"openai-completions",reasoning:false,input:["text"],contextWindow:100000,maxTokens:4000,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}}),
    store:new ProductStore(dbPath,sourcesDir),
    execution:mockExec,
    saveChat:async()=>{},
    saveRun:async()=>{},
  });
  for await(const _event of analyst.stream({q:"Turn 1",thread:"t-ws-1",client:"owner-a"},undefined,"run-budget-test",{runTimeoutMs:12345})){}
  for await(const _event of analyst.stream({q:"Turn 2",thread:"t-ws-1",client:"owner-a"})){}
  for await(const _event of analyst.stream({q:"Anonymous"})){}
  const expectedWs=threadWorkspacePath(privateDir,{owner:"owner-a",thread:"t-ws-1"});
  assert.equal(seenBridgeEnvs[0].cwd,expectedWs);
  assert.equal(seenBridgeEnvs[0].ws,expectedWs);
  assert.equal(seenBridgeEnvs[1].cwd,expectedWs);
  assert.equal(seenBridgeEnvs[1].ws,expectedWs);
  assert.equal(seenHistories[1].at(-1).reasoning,"Turn reasoning");
  assert(existsSync(join(expectedWs,"turn-artifact.txt")));
  assert.notEqual(seenBridgeEnvs[2].ws,expectedWs);
  assert.equal(seenBridgeEnvs[0].timeout,12345);
  assert.equal(seenBridgeEnvs[1].timeout,undefined);
  assert.equal(seenBridgeEnvs[2].timeout,undefined);
  assert(!existsSync(seenBridgeEnvs[2].ws));
  const entries=await readdir(privateDir);
  assert(!entries.some(name=>name.startsWith("pi-")));
});

test("view context serializes into the model-visible turn and the persisted human message",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-viewctx-"));
  try {
    const seenQ=[];
    const saved=[];
    const exec={
      async *stream(ctx){
        seenQ.push(ctx.q);
        yield {type:"answer",text:"done",reasoning:"r"};
        yield {type:"closed"};
      }
    };
    const {analyst}=continuityHarness(dir,exec,{saveChat:async(thread,role,content)=>{saved.push({role,content});}});
    const context={kind:"matchup",summary:"BOS @ NYK, 2025-26 season matchup",entities:{teams:["BOS","NYK"],season:"2025-26",date:"2026-11-27"}};
    await drainEvents(analyst.stream({q:"Who has the edge?",thread:"t-ctx",client:"owner-a",context}));
    assert(seenQ[0].startsWith('<dime-context kind="matchup">'),seenQ[0].slice(0,120));
    assert(seenQ[0].includes('"teams":["BOS","NYK"]'));
    assert(seenQ[0].indexOf("</dime-context>")<seenQ[0].indexOf("Who has the edge?"));
    assert(seenQ[0].endsWith("Who has the edge?"));
    const human=saved.find(row=>row.role === "human");
    assert(human,"persisted human turn recorded");
    assert(human.content.startsWith('<dime-context kind="matchup">'),"persisted human content carries the machine block");
    const bare=[];
    await drainEvents(analyst.stream({q:"plain question",thread:"t-ctx",client:"owner-a",context:null}));
    assert.equal(seenQ.at(-1),"plain question");
    await drainEvents(analyst.stream({q:"oversized",thread:"t-ctx",client:"owner-a",context:{kind:"matchup",summary:"s",entities:{pad:"x".repeat(5000)}}})).then(()=>assert.fail("oversized context must reject")).catch(err=>assert.equal(err.message,"Invalid analyst request"));
  } finally {await rm(dir,{recursive:true,force:true});}
});

function continuitySource(ref,rows=[{value:1}]) {
  return {ref,callId:"call-"+ref,tool:"sql_exec",response:{content:[{type:"text",text:JSON.stringify({rows})}],structuredContent:{rows},isError:false}};
}

function continuityModel() {
  return {id:"fixture",name:"Fixture",provider:"fixture",api:"openai-completions",reasoning:false,input:["text"],contextWindow:100000,maxTokens:4000,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
}

function continuityHarness(dir,execution,overrides={}) {
  const dbPath=join(dir,"conversations.sqlite3"),sourcesDir=join(dir,"sources"),privateDir=join(dir,"private");
  const store=new ProductStore(dbPath,sourcesDir);
  const analyst=createAnalyst({
    env:{...process.env,DIME_PI_PRIVATE_DIR:privateDir,DIME_CONVERSATION_STORE:dbPath,DIME_PI_SOURCES_DIR:sourcesDir,DIME_WAREHOUSE:join(dir,"warehouse.duckdb"),DIME_STATE_DB:join(dir,"state.duckdb")},
    resolveModel:continuityModel,
    store,
    execution,
    saveChat:overrides.saveChat??(async()=>{}),
    saveRun:overrides.saveRun??(async()=>{}),
  });
  return {analyst,store,sourcesDir};
}

async function drainEvents(stream) {
  const events=[];
  for await(const event of stream) events.push(event);
  return events;
}

function continuityRun(n) {
  return "run-"+n.toString(16).padStart(32,"0");
}

test("identified threads replay stored turns and ignore request-supplied history",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-history-"));
  try {
    const contexts=[];
    const execution={async *stream(ctx){
      contexts.push({history:structuredClone(ctx.history)});
      const answer="Stored answer "+contexts.length;
      yield {type:"answer",text:answer,reasoning:"Stored reasoning "+contexts.length};
      yield {type:"closed"};
    }};
    const {analyst,store}=continuityHarness(dir,execution);
    const identity={owner:"owner-a",thread:"thread-a"};
    await drainEvents(analyst.stream({q:"First question",thread:identity.thread,client:identity.owner,history:[{role:"user",content:"request-only question"},{role:"assistant",content:"request-only answer"}]}));
    assert.deepEqual(contexts[0].history,[]);
    await drainEvents(analyst.stream({q:"Second question",thread:identity.thread,client:identity.owner,history:[{role:"user",content:"request-only followup"}]}));
    assert.deepEqual(contexts[1].history,[{role:"user",content:"First question"},{role:"assistant",content:"Stored answer 1",reasoning:"Stored reasoning 1"}]);
    assert(!JSON.stringify(contexts[1].history).includes("request-only"));
    assert.equal(store.read(identity).length,4);
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("follow-up source refs span artifacts while fresh payloads stay run-local",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-sources-"));
  try {
    const contexts=[];
    const execution={async *stream(ctx){
      contexts.push({sources:ctx.sources.map(record=>record.ref)});
      if(ctx.q==="First question") yield {type:"source",record:continuitySource("src-first")};
      if(ctx.q==="Third question") yield {type:"source",record:continuitySource("src-third")};
      yield {type:"answer",text:ctx.q+" answer"};
      yield {type:"closed"};
    }};
    const {analyst,store,sourcesDir}=continuityHarness(dir,execution);
    const identity={owner:"owner-a",thread:"thread-a"};
    const ask=async q=>{
      const events=await drainEvents(analyst.stream({q,thread:identity.thread,client:identity.owner}));
      const final=events.find(event=>event.type==="final_answer");
      assert(final);
      return final;
    };
    const firstFinal=await ask("First question");
    assert.deepEqual(firstFinal.data.carry.source_refs,["src-first"]);
    const secondFinal=await ask("Second question");
    assert.deepEqual(contexts[1].sources,["src-first"]);
    assert.deepEqual(secondFinal.data.carry.source_refs,["src-first"]);
    const secondArtifact=JSON.parse(readFileSync(join(sourcesDir,secondFinal.data.carry.run_id+".json"),"utf8"));
    assert.deepEqual(secondArtifact.sources,[]);
    assert.deepEqual(secondArtifact.source_refs,["src-first"]);
    const thirdFinal=await ask("Third question");
    assert.deepEqual(contexts[2].sources,["src-first"]);
    assert.deepEqual(thirdFinal.data.carry.source_refs,["src-first","src-third"]);
    const thirdArtifact=JSON.parse(readFileSync(join(sourcesDir,thirdFinal.data.carry.run_id+".json"),"utf8"));
    assert.deepEqual(thirdArtifact.sources.map(record=>record.ref),["src-third"]);
    assert.deepEqual(thirdArtifact.source_refs,["src-first","src-third"]);
    assert.deepEqual(store.readSources(identity,thirdFinal.data.carry.run_id).sources.map(record=>record.ref),["src-first","src-third"]);
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("execution-reported failures keep evidence artifacts outside conversation history",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-failure-"));
  try {
    const chats=[],runs=[];
    const execution={async *stream(){
      yield {type:"source",record:continuitySource("src-failure")};
      yield {type:"failure",kind:"fixture_failure",message:"Synthetic failure"};
      yield {type:"closed"};
    }};
    const {analyst,store,sourcesDir}=continuityHarness(dir,execution,{
      saveChat:async(thread,role,content,owner)=>{chats.push({thread,role,content,owner});},
      saveRun:async(thread,question,answer,owner,run)=>{runs.push({thread,question,answer,owner,run});},
    });
    const identity={owner:"owner-a",thread:"thread-a"};
    const runId=continuityRun(15);
    const events=await drainEvents(analyst.stream({q:"Failing question",thread:identity.thread,client:identity.owner},undefined,runId));
    assert(events.some(event=>event.type==="failure"));
    assert(!events.some(event=>event.type==="final_answer"));
    assert.deepEqual(store.read(identity),[]);
    assert.equal(store.references(identity).length,0);
    assert.deepEqual(chats.map(chat=>chat.role),["human"]);
    assert.equal(runs.length,0);
    const artifact=JSON.parse(readFileSync(join(sourcesDir,runId+".json"),"utf8"));
    assert.deepEqual(artifact.sources.map(record=>record.ref),["src-failure"]);
    assert.deepEqual(artifact.source_refs,["src-failure"]);
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("status events pass through the product stream before the final answer",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-status-stream-"));
  try {
    const execution={async *stream(){
      yield {type:"status",text:"Reading the question"};
      yield {type:"tool_call",name:"get_leaders",args:{stat:"pts"}};
      yield {type:"tool_result",name:"get_leaders",status:"ok",rows:10};
      yield {type:"status",text:"Weighing the evidence"};
      yield {type:"answer",text:"Done"};
      yield {type:"closed"};
    }};
    const {analyst}=continuityHarness(dir,execution);
    const events=await drainEvents(analyst.stream({q:"status probe",thread:"t-status",client:"owner-a"},undefined,continuityRun(200)));
    const statuses=events.filter(e=>e.type==="status");
    assert.deepEqual(statuses.map(e=>e.data.text),["Reading the question","Weighing the evidence"]);
    const order=events.map(e=>e.type);
    assert(order.indexOf("status")<order.indexOf("final_answer"),JSON.stringify(order));
    assert(order.lastIndexOf("status")<order.indexOf("final_answer"),JSON.stringify(order));
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("analyst sends the eight newest prior submissions oldest first",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-submissions-"));
  try {
    const contexts=[];
    const execution={async *stream(ctx){
      contexts.push({submissions:structuredClone(ctx.submissions)});
      yield {type:"answer",text:"Tenth answer"};
      yield {type:"closed"};
    }};
    const {analyst,store}=continuityHarness(dir,execution);
    const identity={owner:"owner-a",thread:"thread-a"};
    for(let i=1;i<=9;i++) {
      const run=continuityRun(i),source=continuitySource("src-prior-"+i);
      store.saveSources(run,[source],[source],{blocks:[{text:"Prior answer "+i}]});
      store.append(identity,"Prior question "+i,"Prior answer "+i,run);
    }
    await drainEvents(analyst.stream({q:"Tenth question",thread:identity.thread,client:identity.owner}));
    assert.deepEqual(contexts[0].submissions.map(entry=>entry.run_id),[2,3,4,5,6,7,8,9].map(continuityRun));
    assert.equal(contexts[0].submissions[0].submission.blocks[0].text,"Prior answer 2");
    assert.equal(contexts[0].submissions.at(-1).submission.blocks[0].text,"Prior answer 9");
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("product store keeps the twelve newest completed exchanges",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-cap-"));
  try {
    const store=new ProductStore(join(dir,"conversations.sqlite3"),join(dir,"sources"));
    const identity={owner:"owner-a",thread:"thread-a"};
    for(let i=1;i<=13;i++) store.append(identity,"Question "+i,"Answer "+i,continuityRun(i));
    const history=store.read(identity);
    assert.equal(store.references(identity).length,26);
    assert.equal(history.length,24);
    assert.equal(history[0].content,"Question 2");
    assert.equal(history.at(-1).content,"Answer 13");
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("prior source continuity outlives the twelve-exchange conversation window",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-source-window-"));
  try {
    const store=new ProductStore(join(dir,"conversations.sqlite3"),join(dir,"sources"));
    const identity={owner:"owner-a",thread:"thread-a"};
    for(let i=1;i<=13;i++) {
      const source=continuitySource("src-window-"+i);
      store.saveSources(continuityRun(i),[source],[source]);
      store.append(identity,"Window question "+i,"Window answer "+i,continuityRun(i));
    }
    assert.equal(store.read(identity).length,24);
    assert.deepEqual(store.priorSources(identity).map(record=>record.ref),Array.from({length:13},(_,index)=>"src-window-"+(index+1)));
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

test("branch parent records do not fork the replayed conversation history",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"dime-continuity-branches-"));
  try {
    const store=new ProductStore(join(dir,"conversations.sqlite3"),join(dir,"sources"));
    const identity={owner:"owner-a",thread:"thread-a"};
    store.append(identity,"Branch question 1","Branch answer 1",continuityRun(1));
    const explicit=store.createBranch(identity,2,"rewind-to-first");
    assert.equal(explicit.parent_sequence,2);
    store.append(identity,"Branch question 2","Branch answer 2",continuityRun(2));
    const branches=store.branches(identity);
    assert.equal(branches.length,2);
    assert(branches.every(branch=>branch.parent_sequence===2));
    assert.deepEqual(store.read(identity).map(turn=>turn.role+":"+turn.content),["user:Branch question 1","assistant:Branch answer 1","user:Branch question 2","assistant:Branch answer 2"]);
  } finally {
    await rm(dir,{recursive:true,force:true});
  }
});

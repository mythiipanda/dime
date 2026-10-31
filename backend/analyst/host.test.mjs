import assert from "node:assert/strict";
import {test} from "node:test";
import {createServer} from "node:http";
import {readFileSync} from "node:fs";
import {writeFile,readdir} from "node:fs/promises";
import {join} from "node:path";
import {DatabaseSync} from "node:sqlite";
import {createAnalyst} from "./dist/analyst.js";
import {openProduct,main} from "./dist/host.js";
import {createProductServer} from "./dist/http.js";
const root=process.env.DIME_PI_TEST_ROOT;
assert(root);
const stage=process.env.DIME_HOST_TEST_STAGE ?? "normal";
const requests=[];
let scenario="normal",priorRef,entered;
const provider=createServer(async(req,res)=>{
 let body="";for await(const chunk of req)body+=chunk;
 const request=JSON.parse(body);requests.push(request);
 if(scenario==="model"){res.writeHead(400,{"content-type":"application/json"});res.end(JSON.stringify({error:{message:"fake-key-DO-NOT-ECHO",type:"invalid_request_error"}}));return;}
 res.writeHead(200,{"content-type":"text/event-stream"});
 if(scenario==="abort"){res.write(":waiting\n\n");entered();return;}

 const toolResult=request.messages.some(m=>m.role==="tool");
 const chunk=delta=>res.write("data: "+JSON.stringify({id:"fixture",object:"chat.completion.chunk",created:1,model:"fixture",choices:[{index:0,delta,finish_reason:null}]})+"\n\n");
 const code=scenario==="followup"
 ? `let denied=false;try{await tools.read_source({ref:"unowned"})}catch{denied=true;}const source=await tools.read_source({ref:${JSON.stringify(priorRef)}});return {denied,pts:source.result.rows[0].PTS};`
 : `let denied=false;try{await tools.product_watchlist_add({entity_type:"player",entity_id:"1"});}catch{denied=true;}const bad=await tools.sql_exec({sql:"SELECT missing FROM silver_leaders_pts"});const source=await tools.sql_exec({sql:"SELECT PTS,_source FROM silver_hist_player_seasons ORDER BY PTS"});return {denied,failed:bad.isError,ref:source.ref,pts:source.result.rows[0].PTS};`;
 if(!toolResult)chunk({role:"assistant",tool_calls:[{index:0,id:"call-fixture",type:"function",function:{name:"codemode",arguments:JSON.stringify({code})}}]});else chunk({role:"assistant",content:"Synthetic answer"});
 res.end("data: "+JSON.stringify({id:"fixture",object:"chat.completion.chunk",created:1,model:"fixture",choices:[{index:0,delta:{},finish_reason:toolResult?"stop":"tool_calls"}]})+"\n\ndata: [DONE]\n\n");
});
const listen=server=>new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
const stop=server=>{server.closeAllConnections();return new Promise(resolve=>server.close(resolve));};
const events=text=>text.split("\n\n").filter(s=>s.startsWith("event:")).map(frame=>[frame.split("\n")[0].slice(7),JSON.parse(frame.split("\n")[1].slice(6))]);
test(`Node product host ${stage}`,async()=>{
 await listen(provider);
 const env={...process.env,DIME_PI_PYTHON:process.env.DIME_PI_PYTHON};
 if(stage==="normal") {const old=new DatabaseSync(env.DIME_CONVERSATION_STORE);
 old.exec("CREATE TABLE conversations(owner TEXT NOT NULL,thread TEXT NOT NULL,sequence INTEGER NOT NULL,turn TEXT NOT NULL,PRIMARY KEY(owner,thread,sequence))");
 old.prepare("INSERT INTO conversations VALUES(?,?,?,?)").run("fixture","thread",1,JSON.stringify({role:"user",content:"old-format question"}));old.close();}
 const product=await openProduct(env);
 const model={provider:"fixture",model:"fixture",baseUrl:`http://127.0.0.1:${provider.address().port}/v1`,apiKey:"fake-key-DO-NOT-ECHO",contextWindow:100000,maxTokens:4000};
 const analyst=createAnalyst({env,python:env.DIME_PI_PYTHON,resolveModel:()=>{if(scenario==="configuration")throw new Error("fake-key-DO-NOT-ECHO");return model;},saveChat:async(thread,role,content,owner)=>{await product.data.call("product_save_chat",{thread,role,content,owner});},saveRun:async(thread,question,answer,owner,run_id)=>{await product.data.call("product_save_run",{thread,question,answer,owner,run_id});}});
 const host=createProductServer({env,data:product.data,analyst,manifest:{fixture:true}});await listen(host);
 const url=`http://127.0.0.1:${host.address().port}`;
 const request=async()=>fetch(url+"/api/v2/chat/stream",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({q:"fixture question",client:"fixture",thread:"thread"})});
 try{
  if(stage==="normal") {
  const response=await request();assert.equal(response.status,200);assert.match(response.headers.get("content-type"),/text\/event-stream/);const first=events(await response.text());
  assert(!first.some(([name])=>name==="failure"),JSON.stringify(first));
  const final=first.find(([name])=>name==="final_answer")[1];assert.equal(final.text,"Synthetic answer");
  const sourceUrl=url+`/api/v2/runs/${final.carry.run_id}/sources?thread=thread&client=fixture`;
  const sourceResponse=await fetch(sourceUrl);assert.equal(sourceResponse.status,200);const source=await sourceResponse.json();
  assert.equal(source.sources.length,2);assert(JSON.stringify(source).includes("RAW_SECRET_ROW"));assert(!JSON.stringify(requests).includes("RAW_SECRET_ROW"));
  assert(requests.some(r=>r.messages.some(m=>m.role==="tool"&&/"denied"\s*:\s*true/.test(m.content))));
  assert.equal((await fetch(sourceUrl.replace("client=fixture","client=wrong"))).status,404);
  const ledger=analyst.store.references({owner:"fixture",thread:"thread"});assert.equal(ledger.length,3);assert.equal(ledger[1].run_id,final.carry.run_id);assert.equal(analyst.store.branches({owner:"fixture",thread:"thread"}).length,1);
  await writeFile(join(root,"host-events.json"),JSON.stringify(first));return;
  }
  if(stage==="cli_abort") {scenario="abort";const ready=new Promise(resolve=>{entered=resolve;});const pending=main(["chat","CLI abort fixture"],env,()=>model);await ready;process.emit("SIGINT");await assert.rejects(pending);assert(!(await readdir(env.DIME_PI_PRIVATE_DIR)).some(name=>name.startsWith("pi-")));return;}
  if(stage==="configuration") {scenario="configuration";const result=events(await(await request()).text());assert.equal(result[0][1].kind,"configuration");assert(!JSON.stringify(result).includes("fake-key"));assert.equal(requests.length,0);return;}
  if(stage==="cli") {await main(["chat","CLI fixture question"],env,()=>model);assert(!JSON.stringify(requests).includes("RAW_SECRET_ROW"));return;}
  if(stage==="frontend") {
    globalThis.localStorage={getItem:()=>"fixture",setItem(){}};globalThis.window={localStorage:globalThis.localStorage};
    const originalFetch=globalThis.fetch;globalThis.fetch=(target,init)=>{const parsed=new URL(String(target),url);return originalFetch(parsed.pathname.startsWith("/api/")?url+parsed.pathname+parsed.search:target,init);};
    try {const api=await import("../../frontend/lib/api.ts");const observed=[],errors=[];let done=0;await (api.postChatStream??api.default.postChatStream)("Frontend fixture question",null,{onEvent:(name,data)=>observed.push([name,data]),onDone:()=>done++,onError:error=>errors.push(error)},undefined,"thread");assert.equal(done,1);assert.deepEqual(errors,[]);const final=observed.find(([name])=>name==="final_answer")[1];assert.equal(final.carry.verification,"unassessed");assert(final.carry.sources.length>=2);assert.equal(final.carry.sources.length,final.carry.source_refs.length);}finally{globalThis.fetch=originalFetch;}return;
  }
  if(stage==="model") {const before=analyst.store.references({owner:"fixture",thread:"thread"}).length;scenario="model";const result=events(await(await request()).text());assert(result.some(([name])=>name==="failure"));assert(!JSON.stringify(result).includes("fake-key"));assert.equal(analyst.store.references({owner:"fixture",thread:"thread"}).length,before);return;}
  const final=JSON.parse(readFileSync(join(root,"host-events.json"),"utf8")).find(([name])=>name==="final_answer")[1];
  const source=analyst.store.readSources({owner:"fixture",thread:"thread"},final.carry.run_id);
  if(stage==="followup") {
  priorRef=source.sources[1].ref;scenario="followup";
  const followup=events(await(await request()).text());assert(!followup.some(([name])=>name==="failure"));const next=followup.find(([name])=>name==="final_answer")[1];
  assert.deepEqual(next.carry.source_refs,final.carry.source_refs);const artifact=JSON.parse(readFileSync(join(env.DIME_PI_SOURCES_DIR,next.carry.run_id+".json"),"utf8"));assert.equal(artifact.sources.length,0);
  assert(!JSON.stringify(requests).includes("RAW_SECRET_ROW"));assert(requests.some(r=>JSON.stringify(r).includes("old-format question")));
  const added=await fetch(url+"/api/watchlist",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({entity_type:"player",entity_id:"201939",season:"2090-91"})});assert.equal(added.status,200);assert.equal((await added.json()).ok,true);
  return;
  }
  scenario="abort";const ready=new Promise(resolve=>{entered=resolve;});const controller=new AbortController();const pending=fetch(url+"/api/v2/chat/stream",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({q:"abort"}),signal:controller.signal}).then(r=>r.text()).catch(()=>{});await ready;controller.abort();await pending;
  for(let attempt=0;attempt<100;attempt++){if(!(await readdir(env.DIME_PI_PRIVATE_DIR)).some(name=>name.startsWith("pi-")))break;await new Promise(resolve=>setTimeout(resolve,50));}
  assert(!(await readdir(env.DIME_PI_PRIVATE_DIR)).some(name=>name.startsWith("pi-")),"Disconnected session did not settle");
  scenario="normal";const recovery=events(await(await request()).text());assert(recovery.some(([name])=>name==="final_answer"));
  await writeFile(join(root,"host-requests-"+stage+".json"),JSON.stringify(requests));
 } finally {await writeFile(join(root,"host-requests-"+stage+"-"+Date.now()+".json"),JSON.stringify(requests));await stop(host);await product.data.close();await stop(provider);}
});




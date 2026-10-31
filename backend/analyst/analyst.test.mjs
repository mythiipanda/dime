import assert from "node:assert/strict";
import {test} from "node:test";
import {createServer} from "node:http";
import {mkdir,writeFile} from "node:fs/promises";
import {join} from "node:path";
import {createPiExecution as createAnalyst} from "./dist/pi-execution.js";

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
      ? `let denied=false; try { await tools.read_source({ref:"unowned"}); } catch {denied=true;} const source=await tools.read_source({ref:${JSON.stringify(globalThis.priorRef)}}); return {denied,secretPresent:source.result.rows[1]._source.length === 14,pts:source.result.rows[0].PTS};`
      : `let denied=false; try {await tools.watchlist_add({});} catch {denied=true;} const bad=await tools.sql_exec({sql:"SELECT missing FROM silver_leaders_pts"}); const source=await tools.sql_exec({sql:"SELECT PTS, _source FROM silver_hist_player_seasons ORDER BY PTS"}); return {denied,failed:bad.isError,ref:source.ref,pts:source.result.rows[0].PTS,unit:source.result.declared_column_semantics.PTS.unit};`;
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
  const analyst=createAnalyst();
  try {
    const events=[];
    for await(const event of analyst.stream(context)) events.push(event);
    assert(!events.some(e=>e.type === "failure"),JSON.stringify(events));
    assert.equal(events.find(e=>e.type === "answer")?.text,"Synthetic answer");
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


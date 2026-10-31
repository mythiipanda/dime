import assert from "node:assert/strict";
import {readFileSync,mkdirSync,writeFileSync,utimesSync} from "node:fs";
import {join} from "node:path";
import {DatabaseSync} from "node:sqlite";
import {createAnalyst} from "./dist/analyst.js";
import {createProductServer} from "./dist/http.js";
const root=process.env.DIME_PI_TEST_ROOT;
const cases=JSON.parse(readFileSync(process.argv[2],"utf8"));
const suffix=Date.now();
const env={...process.env,DIME_CONVERSATION_STORE:join(root,`node-conversations-${suffix}.sqlite`),DIME_PROJECT_STORE:join(root,`node-projects-${suffix}.sqlite`),DIME_WORKSPACE_STORE:join(root,`node-workspaces-${suffix}.sqlite`)};
const db=new DatabaseSync(env.DIME_CONVERSATION_STORE);db.exec("CREATE TABLE conversations(owner TEXT NOT NULL,thread TEXT NOT NULL,sequence INTEGER NOT NULL,turn TEXT NOT NULL,run_id TEXT,turn_id TEXT,PRIMARY KEY(owner,thread,sequence))");db.prepare("INSERT INTO conversations VALUES(?,?,?,?,?,?)").run("fixture","thread",1,JSON.stringify({role:"user",content:"old"}),null,null);db.close();
const output=(operation,args)=>({ok:true,rows:{operation,args}});
const data={close:async()=>{},async call(name,args){switch(name){
 case "product_warehouse_health":return {ok:false,reason:"ratings_table_missing"};
 case "product_freshness":return cases.find(c=>c.path==="/api/datasets/freshness").body;
 case "product_dataset":{const fixture=cases.find(c=>c.path===`/api/datasets/${args.name}${args.name==="leaders"?"?season=2090-91":""}`);if(args.fmt==="csv")return {encoding:"base64",media_type:"text/csv",body:Buffer.from(cases.find(c=>c.path.endsWith("fmt=csv")).body).toString("base64")};return fixture.body;}
 case "product_threads":return {threads:[{thread:"thread",owner:args.owner}]};
 case "product_runs":return {runs:[{question:"fixture",answer:"answer",tables:[],thread:args.thread,owner:args.owner}]};
 case "product_rerun":return {ok:true,columns:["PTS"],rows:[[71]],ms:1,capped:false};
 case "product_resolve":return output("resolve",{query:args.query});
 case "product_trade":return output("trade",args);
 case "product_debate":if(args.season==="2025-26")return cases.find(c=>c.path==="/api/debate-card?a=A&b=B").body;return {result:{ok:true,rows:{path:"/private/debate_A_vs_B_1.html",players:["A","B"]}},season:args.season};
 case "product_today":return output("today",args);
 case "product_watchlist":return output("watchlist",args);
 case "product_watchlist_add":return output("watchlist_add",args);
 case "product_watchlist_remove":return output("watchlist_remove",args);
 case "product_movers":return output("movers",args);
 case "product_briefing":return output("briefing",args);
 default:throw new Error("Unexpected operation "+name);
}}};
const analyst=createAnalyst({env,python:process.env.DIME_PI_PYTHON,resolveModel:()=>{throw new Error("configuration fixture");},saveChat:async()=>{},saveRun:async()=>{}});
const cardsDir=join(root,"node-cards");mkdirSync(cardsDir,{recursive:true});writeFileSync(join(cardsDir,"debate_A_vs_B_1.html"),"<h1>Owned fixture</h1>");utimesSync(join(cardsDir,"debate_A_vs_B_1.html"),1000000000,1000000000);
const host=createProductServer({env,data,analyst,cardsDir,manifest:{fixture:true}});await new Promise(resolve=>host.listen(0,"127.0.0.1",resolve));
const url=`http://127.0.0.1:${host.address().port}`;
function normalize(value){
 if(typeof value==="string")return value.replace(/run-[a-f0-9]{32}/g,"run-ID").replace(/project-[a-f0-9]{32}/g,"project-ID").replace(/^[a-f0-9]{32}$/,"ID");
 if(Array.isArray(value))return value.map(normalize);
 if(value&&typeof value==="object")return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,["owner_token","created_at","updated_at"].includes(key)?typeof item:normalize(item)]));
 return value;
}
const failures=[],identities=new Map();
const rewrite=value=>typeof value==="string"?[...identities].reduce((out,[from,to])=>out.replaceAll(from,to),value):value;
try {
 for(const fixture of cases){
  const response=await fetch(url+rewrite(fixture.path),{method:fixture.method,headers:{...Object.fromEntries(Object.entries(fixture.request_headers).map(([key,value])=>[key,rewrite(value)])),...(fixture.request===null?{}:{"content-type":"application/json"})},...(fixture.request===null?{}:{body:JSON.stringify(fixture.request)})});
  const text=await response.text();let body;try{body=JSON.parse(text);}catch{body=text;}
  if(fixture.method==="POST"&&["/api/workspaces","/api/projects"].includes(fixture.path)&&body?.id){identities.set(fixture.body.id,body.id);if(body.owner_token)identities.set(fixture.body.owner_token,body.owner_token);}
  try{
   assert.equal(response.status,fixture.status,"status");
   for(const [name,value] of Object.entries(fixture.headers))assert.equal(response.headers.get(name),name==='access-control-allow-methods'?'GET, POST, PATCH, DELETE':value,name);
   assert.deepEqual(normalize(body),normalize(fixture.body),"body");
  }catch(error){failures.push({path:fixture.path,method:fixture.method,error:error.message,actual:body,expected:fixture.body});}
 }
 writeFileSync(join(root,"new-route-contract-failures-"+Date.now()+".json"),JSON.stringify(failures,null,2));
 assert.equal(failures.length,0,JSON.stringify(failures.map(f=>({path:f.path,error:f.error.slice(0,350)})),null,2));
 console.log(`Paired old/new actual HTTP: ${cases.length} contracts passed`);
 {
  const preflightPatch = await fetch(url + "/api/workspaces/fixture", {
   method: "OPTIONS",
   headers: {
    origin: "http://localhost:3000",
    "access-control-request-method": "PATCH",
    "access-control-request-headers": "content-type, x-owner-token"
   }
  });
  assert.equal(preflightPatch.status, 200);
  assert.equal(preflightPatch.headers.get("access-control-allow-methods"), "GET, POST, PATCH, DELETE");
  assert.equal(preflightPatch.headers.get("access-control-allow-origin"), "http://localhost:3000");
  assert.equal(preflightPatch.headers.get("access-control-allow-headers"), "content-type, x-owner-token");
  assert.equal(await preflightPatch.text(), "OK");

  const badOrigin = await fetch(url + "/api/workspaces/fixture", {
   method: "OPTIONS",
   headers: {
    origin: "http://evil.com",
    "access-control-request-method": "PATCH"
   }
  });
  assert.equal(badOrigin.status, 400);
  assert.equal(await badOrigin.text(), "Disallowed CORS origin");

  const badMethod = await fetch(url + "/api/workspaces/fixture", {
   method: "OPTIONS",
   headers: {
    origin: "http://localhost:3000",
    "access-control-request-method": "PUT"
   }
  });
  assert.equal(badMethod.status, 400);
  assert.equal(await badMethod.text(), "Disallowed CORS method");

  const badBoth = await fetch(url + "/api/workspaces/fixture", {
   method: "OPTIONS",
   headers: {
    origin: "http://evil.com",
    "access-control-request-method": "PUT"
   }
  });
  assert.equal(badBoth.status, 400);
  assert.equal(await badBoth.text(), "Disallowed CORS origin, method");

  for (const m of ["GET", "POST", "DELETE"]) {
   const res = await fetch(url + "/api/workspaces/fixture", {
    method: "OPTIONS",
    headers: {
     origin: "http://localhost:3000",
     "access-control-request-method": m
    }
   });
   assert.equal(res.status, 200, 'preflight ' + m);
   assert.equal(res.headers.get("access-control-allow-methods"), "GET, POST, PATCH, DELETE");
   assert.equal(await res.text(), "OK");
  }

  const malformed = await fetch(url + "/api/workspaces", {
   method: "POST",
   headers: {'content-type': 'application/json'},
   body: "{"
  });
  assert.equal(malformed.status, 422);
  const malformedBody = await malformed.json();
  assert(Array.isArray(malformedBody.detail), "malformed JSON detail must be an array");
  assert.equal(malformedBody.detail.length, 1);
  assert.equal(malformedBody.detail[0].type, "json_invalid");
  assert.equal(malformedBody.detail[0].msg, "JSON decode error");
  assert.deepEqual(malformedBody.detail[0].loc, ["body", 1]);
  assert(typeof malformedBody.detail[0].ctx?.error === "string");
  assert.equal(malformedBody.detail[0].url, "https://errors.pydantic.dev/2.12/v/json_invalid");

  const created = await fetch(url + "/api/workspaces", {
   method: "POST",
   headers: {'content-type': 'application/json'},
   body: JSON.stringify({ name: "flow-ws", owner: "flow-owner" })
  });
  assert.equal(created.status, 201);
  const createdBody = await created.json();
  assert(createdBody.id && createdBody.owner_token);

  const badTokenPatch = await fetch(url + "/api/workspaces/" + createdBody.id, {
   method: "PATCH",
   headers: { "content-type": "application/json", "x-owner-token": "bad-token" },
   body: JSON.stringify({ name: "renamed-fail" })
  });
  assert.equal(badTokenPatch.status, 403);

  const noTokenPatch = await fetch(url + "/api/workspaces/" + createdBody.id, {
   method: "PATCH",
   headers: { "content-type": "application/json" },
   body: JSON.stringify({ name: "renamed-fail" })
  });
  assert.equal(noTokenPatch.status, 401);

  const validPatch = await fetch(url + "/api/workspaces/" + createdBody.id, {
   method: "PATCH",
   headers: { "content-type": "application/json", "x-owner-token": createdBody.owner_token },
   body: JSON.stringify({ name: "flow-ws-renamed" })
  });
  assert.equal(validPatch.status, 200);
  const validPatchBody = await validPatch.json();
  assert.equal(validPatchBody.name, "flow-ws-renamed");

  const getWs = await fetch(url + "/api/workspaces/" + createdBody.id);
  assert.equal(getWs.status, 200);
  const getWsBody = await getWs.json();
  assert.equal(getWsBody.name, "flow-ws-renamed");

  const badTokenDel = await fetch(url + "/api/workspaces/" + createdBody.id, {
   method: "DELETE",
   headers: { "x-owner-token": "bad-token" }
  });
  assert.equal(badTokenDel.status, 403);

  const validDel = await fetch(url + "/api/workspaces/" + createdBody.id, {
   method: "DELETE",
   headers: { "x-owner-token": createdBody.owner_token }
  });
  assert.equal(validDel.status, 200);

  const getDeleted = await fetch(url + "/api/workspaces/" + createdBody.id);
  assert.equal(getDeleted.status, 404);

  console.log("Additional contract corrections: PATCH preflight, CORS rejection, malformed JSON, and workspace flow passed");
 }

}finally{host.closeAllConnections();await new Promise(resolve=>host.close(resolve));}

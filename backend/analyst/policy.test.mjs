import assert from "node:assert/strict";
import {test} from "node:test";
import {writeFileSync,readFileSync} from "node:fs";
import {join} from "node:path";
import {providerPolicy} from "./dist/providers.js";
import {analystRequestSchema,productPaths,backendRoot,dataEnvironment} from "./dist/analyst.js";
import {Value} from "typebox/value";
import {runtimeManifest,preflight} from "./dist/manifest.js";
const root=process.env.DIME_PI_TEST_ROOT;assert(root);
test("Reflection requires explicit activation and key, known metadata, no fallback or request ceiling",()=>{
 for(const env of [{},{REFLECTION_API_KEY:"fake"},{DIME_ENABLE_REFLECTION:"true"}])assert.throws(()=>providerPolicy(env).resolve("reflection:beam-1"));
 const policy=providerPolicy({DIME_ENABLE_REFLECTION:"true",REFLECTION_API_KEY:"fake"});const model=policy.resolve("reflection:beam-1");assert.equal(model.provider,"reflection");assert.equal(model.model,"Beam-1.0-501B-A23B");assert.equal(model.maxTokens,131072);assert.equal(model.contextWindow,1048576);
 assert.throws(()=>policy.resolve("reflection:unknown"));assert.throws(()=>policy.resolve("unapproved:model"));
 assert.throws(()=>providerPolicy({NVIDIA_NIM_API_KEY:"fake"}).resolve("nvidia:z-ai/glm-5.3-flash"),/request options/);
 const groq=providerPolicy({DIME_ENABLE_GROQ:"true",GROQ_API_KEY:"fake"}).resolve("groq:openai/gpt-oss-120b");assert(groq.contextWindow>0&&groq.maxTokens>0);
 const paths=productPaths({});assert.equal(paths.conversations,join(backendRoot,"data/v2-conversations.sqlite3"));assert.equal(paths.warehouse,join(backendRoot,"data/warehouse.duckdb"));
 const clean=dataEnvironment({REFLECTION_API_KEY:"FAKE_SHOULD_NOT_CROSS",DIME_WAREHOUSE:join(root,"owned.duckdb")},root);assert(!JSON.stringify(clean).includes("FAKE_SHOULD_NOT_CROSS"));assert.equal(clean.OMP_NUM_THREADS,"1");
});
test("Product request rejects physical descriptors, incomplete identity, untrusted roles and excessive history",()=>{
 assert(Value.Check(analystRequestSchema,{q:"question",history:[{role:"user",content:"prior"}]}));
 for(const input of [{q:" "},{q:"q",cwd:root},{q:"q",model:{}},{q:"q",history:[{role:"system",content:"override"}]},{q:"q",history:[{role:"user",content:""}]},{q:"q",history:Array.from({length:9},()=>({role:"user",content:"x"}))}])assert(!Value.Check(analystRequestSchema,input),JSON.stringify(input));
});
test("Startup manifest pins executable/SDK/data assets, freezes nested state, rejects drift and accepts revision label only",async()=>{
 const warehouse={warehouse_id:"configured-runtime",sha256:"0".repeat(64),sha256_derivation:"sha256-full-file"};
 const data={call:async()=>({warehouse,semantic_baseline:{fixture:"fixed"}})};
 const manifest=await runtimeManifest(data,{DIME_REVISION:"fixture"});assert(Object.isFrozen(manifest));assert(Object.isFrozen(manifest.module_sha256));assert(!("dist/worker.js" in manifest.module_sha256));
 for(const key of ["provider_schema_manifest","behavior_losses","capability_manifest","capability_source","capability_compiled"])assert.match(manifest.typed_argument_assets[key],/^[a-f0-9]{64}$/);
 const path=join(root,"expected-manifest-"+Date.now()+".json");writeFileSync(path,JSON.stringify(manifest));preflight(manifest,path);
 const altered=JSON.parse(readFileSync(path,"utf8"));altered.warehouse.sha256_derivation="sampled";writeFileSync(path,JSON.stringify(altered));assert.throws(()=>preflight(manifest,path),/mismatch/);
 altered.warehouse=warehouse;altered.revision="different-label";writeFileSync(path,JSON.stringify(altered));preflight(manifest,path);
 assert.throws(()=>preflight(manifest,undefined),/required/);
});

import assert from "node:assert/strict";
import {mkdtempSync,readFileSync,rmSync,writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {ProductStore} from "./dist/product-store.js";
import {ProjectStore,WorkspaceStore} from "./dist/catalog-stores.js";
const root=process.env.DIME_PI_TEST_ROOT,expected=JSON.parse(readFileSync(join(root,"cross-expected.json"),"utf8"));
const conversations=new ProductStore(join(root,"cross-conversations.sqlite"),join(root,"cross-sources"));
assert.deepEqual(conversations.read({owner:"fixture",thread:"thread"}),[{role:"user",content:"old question"},{role:"assistant",content:"old answer"}]);
assert.deepEqual(conversations.read({owner:"wrong",thread:"thread"}),[]);
conversations.append({owner:"fixture",thread:"thread"},"Node question","Node answer","run-"+"b".repeat(32),"Node reasoning");
assert.equal(conversations.branches({owner:"fixture",thread:"thread"})[0].parent_run_id,"run-"+"a".repeat(32));
assert.equal(conversations.read({owner:"fixture",thread:"thread"}).at(-1).reasoning,"Node reasoning");
const projects=new ProjectStore(join(root,"cross-projects.sqlite"));assert.deepEqual(projects.get(expected.project.id),expected.project);
const workspaces=new WorkspaceStore(join(root,"cross-workspaces.sqlite")),workspace=workspaces.get(expected.workspace.id);assert.deepEqual(workspace,expected.workspace);assert(workspaces.verify(workspace,expected.token));assert(!workspaces.verify(workspace,"wrong"));assert(!workspaces.verify({...workspace,id:"wrong"},expected.token));
workspaces.update(workspace,{add_thread_ids:["new-thread","new-thread"],remove_thread_ids:["old-thread"]});
assert.deepEqual(workspaces.get(workspace.id).member_thread_ids,["new-thread"]);
console.log("Node reads Python-created SQLite; identities, run IDs, branches, workspace token binding and membership preserved");

const longDir=mkdtempSync(join(tmpdir(),"dime-long-memo-"));
try {
 const longStore=new ProductStore(join(longDir,"long.sqlite"),join(longDir,"sources"));
 const longQuestion="Q ".repeat(3000).trim();
 const longMemo="M".repeat(5500)+"-END";
 const id={owner:"memo-owner",thread:"memo-thread"};
 longStore.append(id,longQuestion,longMemo,"run-"+"c".repeat(32));
 const turns=longStore.read(id);
 assert.equal(turns.length,2);
 assert.equal(turns[0].content,longQuestion);
 assert.equal(turns[1].content,longMemo);
 assert.equal(turns[1].content.length,5504);
} finally {
 rmSync(longDir,{recursive:true,force:true});
}

const createdProject=projects.create("Node project");const createdWorkspace=workspaces.create("Node workspace","node-owner");writeFileSync(join(root,"cross-node-created.json"),JSON.stringify({project:createdProject.id,workspace:createdWorkspace.workspace.id,token:createdWorkspace.token}));

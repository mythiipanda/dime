"use client";

import { useEffect, useRef, useState } from "react";
import type { ActivityRecord } from "../lib/chat";
import { isNoiseRecord, pairToolItems, planSteps, recordField, recordKey, recordLabel, type PlanStep, type ToolPair } from "../lib/activity";

type View={label:string;meta:string;fields:[string,string][]};
const words=(v:unknown)=>String(v??"").replace(/_/g," ");
const amount=(v:unknown,n:string)=>`${Number(v)||0} ${n}${Number(v)===1?"":"s"}`;
const fmtMs=(ms?:number)=>ms===undefined||ms===null?"":ms<1000?`${ms}ms`:`${(ms/1000).toFixed(1)}s`;
const payload=(i:ActivityRecord)=>i.data.data&&typeof i.data.data==="object"&&!Array.isArray(i.data.data)?i.data.data as Record<string,unknown>:{};
const emittedMs=(v?:string)=>{const t=v?Date.parse(v):NaN;return Number.isFinite(t)?t:undefined};
function pairMs(pair:ToolPair):number|undefined{
  if(pair.result?.durationMs!==undefined)return pair.result.durationMs;
  const topMs=pair.result?recordField(pair.result,"ms"):undefined;
  if(typeof topMs==="number")return topMs;
  const from=pair.call?emittedMs(pair.call.emittedAt):undefined;
  const to=pair.result?emittedMs(pair.result.emittedAt):undefined;
  if(from!==undefined&&to!==undefined&&to>=from)return to-from;
  return undefined;
}
function pairName(pair:ToolPair):string{
  const item=pair.call??pair.result!;
  return words(recordLabel(item)||"data");
}
function pairFailed(pair:ToolPair):boolean{
  const r=pair.result;
  return !!r&&(r.transition==="failed"||r.status==="fail"||r.status==="failed");
}
function pairError(pair:ToolPair):string|undefined{
  const summary=pair.result?.summary;
  if(typeof summary==="string"&&summary)return summary.slice(0,160);
  const v=pair.result?recordField(pair.result,"error"):undefined;
  return typeof v==="string"&&v?v.slice(0,160):undefined;
}
function pairRows(pair:ToolPair):number|undefined{
  if(!pair.result)return undefined;
  const v=recordField(pair.result,"rows");
  return typeof v==="number"?v:undefined;
}
export function describePair(pair:ToolPair,streamRunning:boolean):View{
  const name=pairName(pair);
  const rows=pairRows(pair);
  const ms=pairMs(pair);
  if(!pair.result){
    const argCount=pair.call?recordField(pair.call,"argument_count"):undefined;
    const summary=pair.call?recordField(pair.call,"summary"):undefined;
    const fields:[string,string][]=typeof argCount==="number"?[["Inputs",amount(argCount,"field")]]:typeof summary==="string"&&summary?[["Summary",summary.slice(0,160)]]:[];
    return{label:`Searching ${name}`,meta:streamRunning?"Running":"No result",fields};
  }
  if(pairFailed(pair))return{label:`${name} unavailable`,meta:"Failed",fields:[...(rows===undefined?[]:[["Rows",String(rows)] as [string,string]]),...(ms===undefined?[]:[["Time",fmtMs(ms)] as [string,string]]),...(pairError(pair)?[["Error",pairError(pair)!] as [string,string]]:[])]};
  const meta=[rows===undefined?undefined:amount(rows,"row"),ms===undefined?undefined:fmtMs(ms)].filter(Boolean).join(" · ");
  return{label:`Found ${name}`,meta,fields:[...(rows===undefined?[]:[["Rows",String(rows)] as [string,string]]),...(ms===undefined?[]:[["Time",fmtMs(ms)] as [string,string]])]};
}
function describe(i:ActivityRecord):View{const d=payload(i),get=(k:string)=>recordField(i,k)??d[k],name=words(recordLabel(i)||"data");
  if(i.kind==="stage_summary")return{label:"Mapped the question",meta:amount(get("requirement_count"),"requirement"),fields:[["Mode",words(get("mode"))],["Season",words((get("season") as string)||"Current")],["Entities",String((get("entity_count") as number)??0)]]};
  if(i.kind==="plan_update"){const caps=get("capabilities");return{label:"Planned the research",meta:amount(get("node_count"),"step"),fields:[["Tools",Array.isArray(caps)?caps.map(words).join(", "):"None"],["Unknown",String((get("unknown_capability_count") as number)??0)]]};}
  if(i.kind==="evidence_update"){const ok=i.transition==="admitted";return{label:ok?`Qualified ${name}`:`Set aside ${name}`,meta:ok?amount(get("rows"),"row"):"Rejected",fields:[["Coverage",words(get("coverage"))],["Quality",words(get("qualification"))],["Warnings",String((get("warning_count") as number)??0)],["Source date",words((get("as_of") as string)||"Not supplied")]]};}
  if(i.kind==="verification_update")return{label:`Verified ${Number(get("supported_count"))||0} of ${Number(get("claim_count"))||0} claims`,meta:Number(get("missing_count"))||Number(get("contradiction_count"))?amount(get("missing_count"),"gap"):"Passed",fields:[["Round",words(get("round"))],["Repairs",String((get("repair_count") as number)??0)]]};
  if(i.kind==="node_update")return{label:words(i.node||"Runtime stage"),meta:i.status==="error"?"Failed":i.status==="complete"?"":"Running",fields:[]};
  return{label:i.title,meta:i.summary||"",fields:[]};}
function isBad(item:ActivityRecord):boolean{
  return item.transition==="failed"||item.status==="fail"||item.status==="failed";
}
type RowKind="pair"|"plan"|"single";
interface Row{key:string;kind:RowKind;pair?:ToolPair;steps?:PlanStep[];item?:ActivityRecord}
function buildRows(items:ActivityRecord[]):Row[]{
  const shown=items.filter((i)=>!isNoiseRecord(i));
  const pairs=pairToolItems(shown);
  const pairForCall=new Map<string,ToolPair>();
  const pairForLoneResult=new Map<string,ToolPair>();
  for(const p of pairs){
    if(p.call)pairForCall.set(p.call.eventId,p);
    else if(p.result)pairForLoneResult.set(p.result.eventId,p);
  }
  const latestPlan=shown.filter((i)=>i.kind==="plan_update").at(-1);
  const latestNode=new Map<string,ActivityRecord>();
  for(const i of shown)if(i.kind==="node_update")latestNode.set(i.node||"",i);
  const rows:Row[]=[];
  for(const i of shown){
    if(i.kind==="tool_call"){
      const p=pairForCall.get(i.eventId);
      if(p&&!pairFailed(p))rows.push({key:`pair:${i.eventId}`,kind:"pair",pair:p});
      continue;
    }
    if(i.kind==="tool_result"){
      const p=pairForLoneResult.get(i.eventId);
      if(p&&!pairFailed(p))rows.push({key:`pair:${i.eventId}`,kind:"pair",pair:p});
      continue;
    }
    if(i.kind==="plan_update"){
      if(latestPlan&&i.eventId===latestPlan.eventId)rows.push({key:`plan:${i.eventId}`,kind:"plan",steps:planSteps(shown),item:i});
      continue;
    }
    if(i.kind==="node_update"){
      if(latestNode.get(i.node||"")?.eventId===i.eventId)rows.push({key:`single:${i.eventId}`,kind:"single",item:i});
      continue;
    }
    rows.push({key:`single:${i.eventId}`,kind:"single",item:i});
  }
  return rows;
}
function Mark({bad,active,glyph}:{bad:boolean;active:boolean;glyph:string}){return <span aria-hidden style={{width:15,display:"inline-grid",placeItems:"center",color:bad?"var(--color-ember)":"var(--color-ash-gray)"}}>{active?<span className="activity-orbit"/>:glyph}</span>}
function StepBody({v,item}:{v:View;item:ActivityRecord}){const [tech,setTech]=useState(false);return <div className="activity-detail" style={{margin:"3px 0 7px 26px",padding:"9px 10px",borderRadius:8,background:"var(--color-stone-canvas)"}}><dl style={{display:"flex",gap:7,flexWrap:"wrap",margin:0}}>{v.fields.map(([k,x])=><div key={k} style={{display:"inline-flex",gap:5,padding:"4px 7px",borderRadius:6,border:"1px solid var(--color-stone-border)",fontSize:11}}><dt style={{color:"var(--color-ash-gray)"}}>{k}</dt><dd style={{margin:0,color:"var(--color-warm-gray)"}}>{x}</dd></div>)}</dl><button type="button" hidden={process.env.NODE_ENV === "production"} onClick={()=>setTech(x=>!x)} style={{marginTop:8,padding:0,border:0,background:"none",fontSize:10,color:"var(--color-ash-gray)",cursor:"pointer"}}>{tech?"Hide raw data":"Raw data"}</button>{tech&&<pre style={{margin:"7px 0 0",padding:8,maxHeight:180,overflow:"auto",whiteSpace:"pre-wrap",overflowWrap:"anywhere",borderRadius:6,background:"var(--color-paper-white)",fontSize:9,lineHeight:1.45,color:"var(--color-warm-gray)"}}>{JSON.stringify(item.data,null,2)}</pre>}</div>}
function SingleStep({item,active,index}:{item:ActivityRecord;active:boolean;index:number}){const [open,setOpen]=useState(false),v=describe(item),bad=isBad(item);return <div className="activity-step" style={{animationDelay:`${Math.min(index,8)*36}ms`}}>
  <button type="button" onClick={()=>setOpen(x=>!x)} aria-expanded={open} style={{width:"100%",display:"grid",gridTemplateColumns:"18px minmax(0,1fr) auto",gap:8,alignItems:"center",padding:"5px 0",border:0,background:"none",textAlign:"left",cursor:"pointer"}}><Mark bad={bad} active={active} glyph={bad?"✗":"·"}/><span style={{fontSize:13,color:"var(--color-ink-black)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{v.label}</span>{v.meta?<span className={active?"activity-shimmer":""} style={{padding:"3px 7px",borderRadius:6,background:"var(--color-stone-canvas)",fontSize:11,color:"var(--color-ash-gray)",whiteSpace:"nowrap"}}>{v.meta}</span>:null}</button>
  {open&&<StepBody v={v} item={item}/>}</div>}
function PairStep({pair,active,index,streamRunning}:{pair:ToolPair;active:boolean;index:number;streamRunning:boolean}){const [open,setOpen]=useState(false),v=describePair(pair,streamRunning),bad=pairFailed(pair);return <div className="activity-step" style={{animationDelay:`${Math.min(index,8)*36}ms`}}>
  <button type="button" onClick={()=>setOpen(x=>!x)} aria-expanded={open} style={{width:"100%",display:"grid",gridTemplateColumns:"18px minmax(0,1fr) auto",gap:8,alignItems:"center",padding:"5px 0",border:0,background:"none",textAlign:"left",cursor:"pointer"}}><Mark bad={bad} active={active&&!pair.result} glyph={bad?"✗":pair.result?"·":"⌕"}/><span style={{fontSize:13,color:"var(--color-ink-black)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{v.label}</span>{v.meta?<span className={active&&!pair.result?"activity-shimmer":""} style={{padding:"3px 7px",borderRadius:6,background:"var(--color-stone-canvas)",fontSize:11,color:bad?"var(--color-ember)":"var(--color-ash-gray)",whiteSpace:"nowrap"}}>{v.meta}</span>:null}</button>
  {open&&pair.result&&<StepBody v={v} item={pair.result}/>}{open&&!pair.result&&pair.call&&<StepBody v={v} item={pair.call}/>}</div>}
function PlanBlock({steps,item,active,index}:{steps:PlanStep[];item:ActivityRecord;active:boolean;index:number}){const [open,setOpen]=useState(true);const done=steps.filter((s)=>s.state==="done").length;return <div className="activity-step" style={{animationDelay:`${Math.min(index,8)*36}ms`}}>
  <button type="button" onClick={()=>setOpen(x=>!x)} aria-expanded={open} style={{width:"100%",display:"grid",gridTemplateColumns:"18px minmax(0,1fr) auto",gap:8,alignItems:"center",padding:"5px 0",border:0,background:"none",textAlign:"left",cursor:"pointer"}}><Mark bad={false} active={active&&done<steps.length} glyph="·"/><span style={{fontSize:10,fontWeight:600,letterSpacing:".08em",textTransform:"uppercase",color:"var(--color-ash-gray)"}}>Plan</span><span style={{padding:"3px 7px",borderRadius:6,background:"var(--color-stone-canvas)",fontSize:11,color:"var(--color-ash-gray)",whiteSpace:"nowrap"}}>{steps.length?`${done} of ${steps.length} done`:describe(item).meta}</span></button>
  {open&&<div className="activity-detail" style={{margin:"3px 0 7px 26px",display:"flex",flexDirection:"column",gap:2}}>{steps.map((s)=><div key={s.capability} style={{display:"grid",gridTemplateColumns:"18px minmax(0,1fr)",gap:8,alignItems:"center",padding:"3px 0"}}><Mark bad={false} active={s.state==="running"} glyph={s.state==="done"?"·":"○"}/><span style={{fontSize:12,color:s.state==="pending"?"var(--color-ash-gray)":"var(--color-ink-black)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{words(s.capability)}</span></div>)}</div>}</div>}
export default function ActivityTimeline({items,running}:{items:ActivityRecord[];running:boolean}){const [open,setOpen]=useState(false),box=useRef<HTMLDivElement>(null);const rows=buildRows(items);useEffect(()=>{if(open&&box.current&&typeof box.current.scrollTo==="function")box.current.scrollTo({top:box.current.scrollHeight,behavior:"smooth"})},[items.length,open]);const pairCount=rows.filter((r)=>r.kind==="pair").length,evidence=rows.filter((r)=>r.kind==="single"&&r.item?.kind==="evidence_update"&&r.item.transition==="admitted").length;const completed=!running&&rows.length>0;
  const latestLabel=():string=>{
    const last=rows.at(-1);
    if(!last)return"Analyzing";
    if(last.kind==="pair"&&last.pair)return describePair(last.pair,running).label;
    if(last.kind==="plan"&&last.steps){const cur=last.steps.find((s)=>s.state==="running");return cur?words(cur.capability):"Analyzing";}
    return last.item?describe(last.item).label:"Analyzing";
  };
  return <>
  <style jsx global>{`@keyframes activity-in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}@keyframes activity-orbit{to{transform:rotate(360deg)}}@keyframes activity-shimmer{0%,100%{opacity:.48}50%{opacity:1}}.activity-step{opacity:0;animation:activity-in .28s cubic-bezier(.2,.8,.2,1) forwards}.activity-detail{animation:activity-in .18s ease-out}.activity-orbit{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--color-stone-border);border-top-color:var(--color-cyan-signal);animation:activity-orbit .8s linear infinite}.activity-shimmer{animation:activity-shimmer 1.35s ease-in-out infinite}.activity-timeline{position:relative;padding-top:3px}.activity-progress-rail{position:absolute;top:0;left:0;width:100%;height:2px;overflow:hidden;border-radius:999px;background:var(--color-stone-border)}.activity-progress-rail::after{content:"";position:absolute;inset:0;width:34%;border-radius:inherit;background:var(--color-cyan-signal);opacity:0;transform:translateX(-110%)}.activity-timeline.is-running .activity-progress-rail::after{opacity:1;animation:activity-progress 1.2s cubic-bezier(.4,0,.2,1) infinite}.activity-timeline.is-complete .activity-progress-rail::after{width:100%;opacity:.55;transform:none;transition:width .28s cubic-bezier(.16,1,.3,1),opacity .2s ease}@keyframes activity-progress{to{transform:translateX(395%)}}@media(prefers-reduced-motion:reduce){.activity-step,.activity-detail,.activity-orbit,.activity-shimmer,.activity-progress-rail::after{animation:none!important;transition:none!important;opacity:1!important}.activity-timeline.is-running .activity-progress-rail::after{width:42%;transform:none}}`}</style>
  <div className={`activity-timeline ${running?"is-running":completed?"is-complete":""}`}><span className="activity-progress-rail" aria-hidden="true"/><button type="button" onClick={()=>setOpen(x=>!x)} aria-expanded={open} style={{display:"inline-flex",alignItems:"center",gap:7,padding:"5px 9px",border:0,borderRadius:7,background:"var(--color-stone-canvas)",color:"var(--color-warm-gray)",fontSize:12,cursor:"pointer"}}><span style={{transform:open?"rotate(90deg)":"none",transition:"transform .16s"}}>›</span>{running?(rows.length?latestLabel():"Analyzing"):`${pairCount} tool call${pairCount===1?"":"s"}`}{!running&&evidence>0?`, ${evidence} source${evidence===1?"":"s"} checked`:""}</button>
  {open&&<div ref={box} role="log" aria-live="polite" aria-label="Tool activity" style={{marginTop:8,maxHeight:390,overflowY:"auto",padding:"0 2px 2px 7px",borderLeft:"1px solid var(--color-stone-border)"}}>{rows.map((r,n)=>r.kind==="pair"&&r.pair?<PairStep key={r.key} pair={r.pair} index={n} streamRunning={running} active={running&&n===rows.length-1}/>:r.kind==="plan"&&r.steps&&r.item?<PlanBlock key={r.key} steps={r.steps} item={r.item} index={n} active={running}/>:r.item?<SingleStep key={r.key} item={r.item} index={n} active={running&&n===rows.length-1}/>:null)}</div>}</div></>}

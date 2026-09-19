"use client";

import { useEffect, useRef, useState } from "react";
import type { ActivityRecord } from "../lib/chat";

type Kind = "plan" | "search" | "evidence" | "check";
type View = { label: string; note: string; kind: Kind; fields: [string,string][] };
const words=(v:unknown)=>String(v??"").replace(/_/g," ");
const amount=(v:unknown,n:string)=>`${Number(v)||0} ${n}${Number(v)===1?"":"s"}`;
const data=(i:ActivityRecord)=>i.data.data&&typeof i.data.data==="object"&&!Array.isArray(i.data.data)?i.data.data as Record<string,unknown>:{};
function view(i:ActivityRecord):View {
 const d=data(i), name=words(d.name||d.capability||"data");
 if(i.kind==="stage_summary")return{label:"Question mapped",note:`${words(d.mode||"quick")} analysis · ${amount(d.requirement_count,"requirement")}`,kind:"plan",fields:[["Entities",String(d.entity_count??0)],["Season",words(d.season||"Current")],["Calculations",String(d.calculation_count??0)]]};
 if(i.kind==="plan_update")return{label:"Research plan ready",note:`${amount(d.node_count,"step")} · ${Array.isArray(d.capabilities)?d.capabilities.map(words).join(", "):"No tools"}`,kind:"plan",fields:[["Known tools",String(Array.isArray(d.capabilities)?d.capabilities.length:0)],["Unknown tools",String(d.unknown_capability_count??0)]]};
 if(i.kind==="tool_call")return{label:`Searching ${name}`,note:"Query in progress",kind:"search",fields:[["Inputs",amount(d.argument_count,"field")],["Unrecognized",String(d.unknown_argument_count??0)]]};
 if(i.kind==="tool_result"){const bad=i.transition==="failed"||i.status==="fail"||i.status==="failed";return{label:bad?`${name} unavailable`:`Found ${name}`,note:bad?"No usable result":d.rows==null?"Query complete":amount(d.rows,"row"),kind:"search",fields:[["Status",bad?"Failed":"Complete"],...(d.rows==null?[]:[["Rows",String(d.rows)] as [string,string]])]};}
 if(i.kind==="evidence_update"){const ok=i.transition==="admitted";return{label:ok?`${name} added to evidence`:`${name} set aside`,note:ok?`${amount(d.rows,"row")} qualified`:"Did not meet the evidence bar",kind:"evidence",fields:[["Coverage",words(d.coverage)],["Quality",words(d.qualification)],["Warnings",String(d.warning_count??0)],["Source date",words(d.as_of||"Not supplied")]]};}
 if(i.kind==="verification_update")return{label:`${Number(d.supported_count)||0} of ${Number(d.claim_count)||0} claims verified`,note:Number(d.missing_count)||Number(d.contradiction_count)?`${amount(d.missing_count,"gap")} · ${amount(d.contradiction_count,"conflict")}`:"Evidence checks passed",kind:"check",fields:[["Round",words(d.round)],["Repairs",String(d.repair_count??0)]]};
 return{label:i.title,note:i.summary||"",kind:"plan",fields:[]};
}
const glyph:Record<Kind,React.ReactNode>={
 plan:<><path d="M4 4h8M4 8h8M4 12h5"/></>,
 search:<><circle cx="6.5" cy="6.5" r="3.5"/><path d="m9 9 4 4"/></>,
 evidence:<><path d="M3 3h10v10H3z"/><path d="m5 8 2 2 4-5"/></>,
 check:<><path d="m2.5 8 3 3 8-8"/></>,
};
function Row({item,active}:{item:ActivityRecord;active:boolean}){
 const [open,setOpen]=useState(false),[tech,setTech]=useState(false);const v=view(item);const bad=item.transition==="failed"||item.status==="fail"||item.status==="failed";
 return <div style={{borderTop:"1px solid var(--color-stone-border)"}}>
  <button type="button" aria-expanded={open} onClick={()=>setOpen(x=>!x)} style={{width:"100%",display:"grid",gridTemplateColumns:"28px minmax(0,1fr) auto",alignItems:"center",gap:11,padding:"12px 14px",border:0,background:"transparent",textAlign:"left",cursor:"pointer"}}>
   <span aria-hidden style={{width:26,height:26,borderRadius:7,display:"grid",placeItems:"center",background:bad?"color-mix(in srgb,var(--color-ember) 10%,transparent)":"var(--color-stone-canvas)",color:bad?"var(--color-ember)":"var(--color-warm-gray)",border:"1px solid var(--color-stone-border)"}}>{active?<span className="pulse-dot" style={{width:7,height:7,borderRadius:99,background:"var(--color-cyan-signal)"}}/>:<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round">{glyph[v.kind]}</svg>}</span>
   <span style={{minWidth:0}}><span style={{display:"block",fontSize:12.5,fontWeight:560,color:"var(--color-ink-black)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{v.label}</span><span style={{display:"block",marginTop:2,fontSize:11.5,color:"var(--color-ash-gray)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{v.note}</span></span>
   <span style={{display:"flex",alignItems:"center",gap:8,color:"var(--color-ash-gray)",fontSize:10.5}}>{active&&<span>Live</span>}<span aria-hidden style={{fontSize:16,transform:open?"rotate(45deg)":"none",transition:"transform .16s"}}>+</span></span>
  </button>
  {open&&<div style={{margin:"-1px 14px 13px 57px",padding:"11px 12px",borderRadius:10,background:"var(--color-stone-canvas)",border:"1px solid var(--color-stone-border)"}}>
   <dl style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(105px,1fr))",gap:"10px 16px",margin:0}}>{v.fields.map(([k,x])=><div key={k}><dt style={{fontSize:9.5,letterSpacing:".055em",textTransform:"uppercase",color:"var(--color-ash-gray)"}}>{k}</dt><dd style={{margin:"3px 0 0",fontSize:11.5,color:"var(--color-warm-gray)"}}>{x}</dd></div>)}</dl>
   <button type="button" onClick={()=>setTech(x=>!x)} style={{marginTop:v.fields.length?11:0,padding:0,border:0,background:"none",fontSize:10.5,color:"var(--color-ash-gray)",cursor:"pointer"}}>{tech?"Hide technical data":"View technical data"} <span aria-hidden>↗</span></button>
   {tech&&<pre style={{margin:"9px 0 0",padding:10,maxHeight:220,overflow:"auto",whiteSpace:"pre-wrap",overflowWrap:"anywhere",borderRadius:8,background:"var(--color-paper-white)",border:"1px solid var(--color-stone-border)",fontSize:10,lineHeight:1.45,color:"var(--color-warm-gray)"}}>{JSON.stringify(item.data,null,2)}</pre>}
  </div>}
 </div>;
}
export default function ActivityTimeline({items,running}:{items:ActivityRecord[];running:boolean}){
 const box=useRef<HTMLDivElement>(null),[follow,setFollow]=useState(true),[seen,setSeen]=useState(items.length);useEffect(()=>{if(follow&&box.current){box.current.scrollTo({top:box.current.scrollHeight,behavior:"smooth"});setSeen(items.length)}},[items.length,follow]);
 const unseen=Math.max(0,items.length-seen);
 return <section style={{border:"1px solid var(--color-stone-border)",borderRadius:12,background:"var(--color-paper-white)",overflow:"hidden"}}>
  <div ref={box} role="log" aria-live="polite" aria-label="Live analysis activity" onScroll={e=>{const x=e.currentTarget,b=x.scrollHeight-x.scrollTop-x.clientHeight<24;setFollow(b);if(b)setSeen(items.length)}} style={{maxHeight:running?390:520,overflowY:"auto"}}>{items.map((i,n)=><Row key={i.eventId} item={i} active={running&&n===items.length-1}/>)}</div>
  {!follow&&unseen>0&&<button type="button" onClick={()=>{setFollow(true);setSeen(items.length)}} style={{width:"100%",padding:8,border:0,borderTop:"1px solid var(--color-stone-border)",background:"var(--color-stone-canvas)",fontSize:11,color:"var(--color-warm-gray)",cursor:"pointer"}}>{unseen} new update{unseen===1?"":"s"}</button>}
 </section>;
}

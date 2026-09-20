"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BACKEND } from "../lib/chat";
import { pinToTray, readTray } from "./CompareTray";

interface Hit { kind: string; id: number | string; name: string; }
interface PaletteItem { id: string; group: string; label: string; hint: string; run: () => void; }
const SECTIONS=[
  {label:"League leaders",hash:"explore-leaders"},{label:"Shot charts",hash:"explore-shots"},
  {label:"Trade checker",hash:"explore-trade"},{label:"Crew lineups",hash:"explore-lineups"},{label:"Playoffs",hash:"explore-playoffs"},
];

export default function CommandPalette({onAsk,onTab,onDebate,openKey=0}:{onAsk:(q:string)=>void;onTab:(t:"chat"|"data")=>void;onDebate?:()=>void;openKey?:number}) {
  const [open,setOpen]=useState(false),[q,setQ]=useState(""),[hits,setHits]=useState<Hit[]>([]),[active,setActive]=useState(0);
  const input=useRef<HTMLInputElement>(null);
  useEffect(()=>{if(openKey>0)setOpen(true)},[openKey]);
  useEffect(()=>{const fn=(e:KeyboardEvent)=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();setOpen(o=>!o)}if(e.key==="Escape")setOpen(false)};window.addEventListener("keydown",fn);return()=>window.removeEventListener("keydown",fn)},[]);
  useEffect(()=>{if(open)setTimeout(()=>input.current?.focus(),30);else{setQ("");setActive(0)}},[open]);
  useEffect(()=>{if(!open||q.trim().length<2){setHits([]);return}const t=setTimeout(async()=>{try{const res=await fetch(`${BACKEND}/api/v1/resolve?q=${encodeURIComponent(q.trim())}`),data=await res.json() as {rows?:{players?:{id:number;full_name:string}[];teams?:{id:number;full_name:string}[]}};setHits([...(data.rows?.players||[]).slice(0,4).map(p=>({kind:"player",id:p.id,name:p.full_name})),...(data.rows?.teams||[]).slice(0,4).map(x=>({kind:"team",id:x.id,name:x.full_name}))])}catch{setHits([])}},250);return()=>clearTimeout(t)},[q,open]);
  const close=()=>setOpen(false),needle=q.trim().toLowerCase(),tray=readTray();
  const items=useMemo<PaletteItem[]>(()=>{
    const out:PaletteItem[]=[
      {id:"chat",group:"Navigate",label:"Analyst chat",hint:"view",run:()=>{onTab("chat");close()}},
      {id:"data",group:"Navigate",label:"Explore datasets",hint:"view",run:()=>{onTab("data");close()}},
      ...SECTIONS.map(s=>({id:s.hash,group:"Explore",label:s.label,hint:"section",run:()=>{onTab("data");close();setTimeout(()=>document.getElementById(s.hash)?.scrollIntoView({behavior:"smooth"}),80)}})),
      ...(onDebate?[{id:"debate",group:"Actions",label:"New debate card",hint:"action",run:()=>{onDebate();close()}}]:[]),
      ...(tray.length>=2?[{id:"tray",group:"Actions",label:`Compare ${tray.join(" vs ")}`,hint:"action",run:()=>{onTab("chat");onAsk(`Compare ${tray.join(" and ")} this season`);close()}}]:[]),
      ...hits.map(h=>({id:`${h.kind}-${h.id}`,group:h.kind==="player"?"Players":"Teams",label:h.name,hint:h.kind,run:()=>{onTab("chat");onAsk(`Tell me about ${h.name}`);close()}})),
    ];return out.filter(x=>!needle||x.label.toLowerCase().includes(needle));
  },[needle,hits,onAsk,onTab,onDebate,tray]);
  useEffect(()=>setActive(0),[needle,hits.length]);
  if(!open)return null;
  const groups=[...new Set(items.map(x=>x.group))];
  return <div className="command-backdrop" onClick={close} role="presentation">
    <div className="command-panel" role="dialog" aria-modal="true" aria-label="Search commands and players" onClick={e=>e.stopPropagation()}>
      <div className="command-search"><span aria-hidden>⌕</span><input ref={input} value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==="ArrowDown"){e.preventDefault();setActive(x=>Math.min(x+1,items.length-1))}if(e.key==="ArrowUp"){e.preventDefault();setActive(x=>Math.max(x-1,0))}if(e.key==="Enter"&&items[active]){e.preventDefault();items[active].run()}}} placeholder="Player, team, section, or action..." aria-controls="command-results" aria-activedescendant={items[active]?.id}/><kbd>Esc</kbd></div>
      <div id="command-results" className="command-results" role="listbox">
        {groups.map(group=><section key={group}><h2>{group}</h2>{items.filter(x=>x.group===group).map(item=>{const index=items.indexOf(item);return <button id={item.id} key={item.id} role="option" aria-selected={index===active} className={index===active?"is-active":""} onMouseEnter={()=>setActive(index)} onClick={item.run}><span>{item.label}</span><small>{item.hint}</small>{item.hint==="player"&&<b onClick={e=>{e.stopPropagation();pinToTray(item.label)}}>+ tray</b>}</button>})}</section>)}
        {!items.length&&<div className="command-empty">No matching players, teams, or actions.</div>}
      </div><footer><span>↑↓ move</span><span>↵ open</span><span>esc close</span></footer>
    </div>
  </div>;
}

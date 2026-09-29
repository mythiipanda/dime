"use client";

import type { ReactNode } from "react";


export function PanelHeader({
  kicker,
  title,
  action,
}: {
  kicker: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="panel-head">
      <div>
        <div className="panel-kicker">{kicker}</div>
        <h2 className="panel-title">{title}</h2>
      </div>
      {action ? <div className="panel-head-action">{action}</div> : null}
    </div>
  );
}


export default function ExplorePanel({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  return (
    <div id={id} className="explore-panel-anchor">
      <section className="card explore-panel-card">{children}</section>
    </div>
  );
}

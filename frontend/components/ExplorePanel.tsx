"use client";

import type { ReactNode } from "react";
/**
 * Shared Explore panel chrome (redesign brief Phase A):
 * kicker (10px/600/.08em) + 16px/500 title, with one action slot.
 * Every Explore panel should use this instead of its own header pattern.
 */


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
/**
 * Card wrapper for an Explore panel with the scroll anchor.
 * `id` is the explore-<section> anchor the sticky nav jumps to.
 */


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

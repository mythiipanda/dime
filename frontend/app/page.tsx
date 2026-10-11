import type { Metadata } from "next";
import DimeHarness from "@/components/site/DimeHarness";
import WorkspaceShell from "@/components/site/WorkspaceShell";
import styles from "./scrollbars.module.css";

export const metadata: Metadata = {
  title: "dime",
  description: "An AI analyst workbench for NBA data.",
};

export default function DimePage() {
  return (
    <WorkspaceShell active="chat">
      <div className={`${styles.scope} flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden`}>
        <DimeHarness />
      </div>
    </WorkspaceShell>
  );
}

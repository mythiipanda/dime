import type { Metadata } from "next";
import DimeHarness from "@/components/site/DimeHarness";
import styles from "./scrollbars.module.css";

export const metadata: Metadata = {
  title: "Dime",
  description: "An AI analyst workbench for NBA data.",
};

export default function DimePage() {
  return (
    <div className={styles.scope}>
      <DimeHarness />
    </div>
  );
}

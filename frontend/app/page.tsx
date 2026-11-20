import { DimeShell } from "../components/shell/DimeShell";

export default function Home() {
  return <DimeShell />;
=======
import type { Metadata } from "next";
import { DimeShell } from "@/components/shell/DimeShell";
import styles from "./scrollbars.module.css";

export const metadata: Metadata = {
  title: "dime",
  description: "An AI analyst workbench for NBA data.",
};

export default function DimePage() {
  return (
    <div className={styles.scope}>
      <DimeShell />
    </div>
  );
>>>>>>> origin/dev
}

import { Archive } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function WarehousePage() {
  return <SurfaceEmptyState name="Warehouse" eyebrow="NBA data" description="Browse the tables behind your analysis and see what each dataset contains." action="Explore the league" href="/explore" icon={Archive} />;
}

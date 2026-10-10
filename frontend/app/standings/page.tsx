import { Trophy } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function StandingsPage() {
  return <SurfaceEmptyState name="Standings" eyebrow="League table" description="Check where every team sits and what the standings mean for the playoff race." action="Explore team data" href="/explore" icon={Trophy} />;
}

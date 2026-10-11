import { Trophy } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function StandingsPage() {
  return <SurfaceEmptyState name="Standings" eyebrow="Not available yet" description="Standings is not available yet." action="Back to Chat" href="/" icon={Trophy} />;
}

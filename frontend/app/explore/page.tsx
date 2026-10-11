import { Compass } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function ExplorePage() {
  return <SurfaceEmptyState name="Explore" eyebrow="League-wide discovery" description="Find a player, team, or trend and follow the evidence wherever it leads." action="Ask about the league" href="/" icon={Compass} />;
}

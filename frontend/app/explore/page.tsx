import { Compass } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function ExplorePage() {
  return <SurfaceEmptyState name="Explore" eyebrow="Not available yet" description="Explore is not available yet." action="Back to Chat" href="/" icon={Compass} />;
}

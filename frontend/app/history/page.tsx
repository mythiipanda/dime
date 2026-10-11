import { History } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function HistoryPage() {
  return <SurfaceEmptyState name="History" eyebrow="Not available yet" description="History is not available yet." action="Back to Chat" href="/" icon={History} />;
}

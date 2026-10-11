import { BookOpen } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function NotebookPage() {
  return <SurfaceEmptyState name="Notebook" eyebrow="Not available yet" description="Notebook is not available yet." action="Back to Chat" href="/" icon={BookOpen} />;
}

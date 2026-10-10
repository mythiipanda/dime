import { BookOpen } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function NotebookPage() {
  return <SurfaceEmptyState name="Notebook" eyebrow="Working papers" description="Build a lasting record of your research, with notes and evidence in one place." action="Ask a question in Chat" href="/" icon={BookOpen} />;
}

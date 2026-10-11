import { History } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function HistoryPage() {
  return <SurfaceEmptyState name="History" eyebrow="Your work" description="Return to past conversations and notebooks when you want to pick up a thread." action="Start a conversation" href="/" icon={History} />;
}

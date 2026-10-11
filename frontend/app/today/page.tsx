import { CalendarDays } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function TodayPage() {
  return <SurfaceEmptyState name="Today" eyebrow="Not available yet" description="Today is not available yet." action="Back to Chat" href="/" icon={CalendarDays} />;
}

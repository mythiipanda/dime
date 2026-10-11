import { CalendarDays } from "lucide-react";
import SurfaceEmptyState from "@/components/site/SurfaceEmptyState";

export default function TodayPage() {
  return <SurfaceEmptyState name="Today" eyebrow="Daily briefing" description="Your NBA day starts here, with the matchups and questions worth your attention." action="Start an analysis" href="/" icon={CalendarDays} />;
}

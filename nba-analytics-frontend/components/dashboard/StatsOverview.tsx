import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Users,
  Calendar,
  Trophy,
  BarChart2,
} from "lucide-react";
import { cn } from "@/lib/utils"; // Import cn

// Define a type for the stat items for better structure and potential reuse
type StatItem = {
  title: string;
  icon: React.ElementType; // Use ElementType for component type
  value: string;
  description: string;
}

const statItems: StatItem[] = [
  {
    title: "Total Players Analyzed",
    icon: Users,
    value: "450+",
    description: "Active NBA players"
  },
  {
    title: "Games Tracked",
    icon: Calendar,
    value: "1,230",
    description: "2023-24 season"
  },
  {
    title: "Teams Covered",
    icon: Trophy,
    value: "30",
    description: "All NBA teams"
  },
  {
    title: "Data Points",
    icon: BarChart2,
    value: "1M+",
    description: "Statistical entries"
  }
];

export function StatsOverview() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {statItems.map((item, index) => { // Added index for animation delay
        const IconComponent = item.icon;
        return (
          <Card
            key={item.title}
            className={cn(
              "transition-all duration-300 hover:scale-[1.03] hover:shadow-md", // Added hover effects
              "animate-in fade-in-0 slide-in-from-bottom-4 duration-500" // Added entrance animation
            )}
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{item.title}</CardTitle> {/* Changed font-regular to font-medium */}
              <IconComponent className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{item.value}</div>
              <p className="text-sm font-regular text-muted-foreground">{item.description}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
} 
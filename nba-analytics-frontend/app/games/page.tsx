import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

// Placeholder page for Games section
export default function GamesPage() {
  return (
    // This content will be rendered within the RootLayout
    <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
      <div className="flex items-center">
        <h1 className="text-lg font-semibold md:text-2xl">Games</h1>
      </div>
      <ScrollArea className="flex-1 rounded-lg border p-4">
        <p className="text-muted-foreground mb-4">
          This section will display game schedules, box scores, and potentially live game data.
        </p>
        {/* Placeholder Content */}
        <div className="grid gap-4 md:grid-cols-2">
           <Card>
             <CardHeader>
               <CardTitle>Today's Games</CardTitle>
             </CardHeader>
             <CardContent>
               <p>Placeholder for today's game schedule/scoreboard.</p>
             </CardContent>
           </Card>
           <Card>
             <CardHeader>
               <CardTitle>Game Finder</CardTitle>
             </CardHeader>
             <CardContent>
               <p>Placeholder for game search/filtering.</p>
             </CardContent>
           </Card>
        </div>
      </ScrollArea>
    </main>
  );
}
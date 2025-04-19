import Scoreboard from '@/components/games/Scoreboard';
import DateNavigator from '@/components/games/DateNavigator';
import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';

// Define the props type for the page
interface GamesPageProps {
  searchParams?: { 
    date?: string; 
  };
}

// Update component signature to accept props
export default async function GamesServerPage({ searchParams }: GamesPageProps) {
  // Function to parse date safely
  const getTargetDate = (dateParam?: string): Date => {
    if (typeof dateParam === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateParam)) {
      try {
        // Attempt to create a date object. Handle potential invalid dates.
        const parsedDate = new Date(dateParam + 'T00:00:00'); // Add time part for consistency
        if (!isNaN(parsedDate.getTime())) {
          return parsedDate;
        }
      } catch (e) {
        console.error("Error parsing date parameter:", e);
      }
    }
    return new Date(); // Default to today if param is missing, invalid, or causes error
  };

  // Get the date string directly from the correctly passed props
  const dateParam = searchParams?.date;
  const targetDate = getTargetDate(dateParam);
  const dateString = targetDate.toISOString().split('T')[0]; // Format as YYYY-MM-DD

  return (
    <div className="flex flex-col h-full p-4 md:p-6 space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">NBA Games</h1>
      
      {/* Date Navigator - Client Component */}
      <DateNavigator currentDate={dateString} />

      {/* Scoreboard - Server Component wrapped in Suspense */}
      <div className="flex-grow overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
        <Suspense 
          key={dateString} // Add key to force re-render on date change
          fallback={ <ScoreboardLoading /> }
        >
          {/* Pass dateString to Scoreboard */}
          <Scoreboard gameDate={dateString} />
        </Suspense>
      </div>
    </div>
  );
}

// Simple loading component for Scoreboard
const ScoreboardLoading = () => (
  <div className="flex items-center justify-center h-60 text-muted-foreground">
    <Loader2 className="mr-3 h-6 w-6 animate-spin text-primary" />
    <span>Loading games...</span>
  </div>
);

// Error: Route "/games" used `searchParams.date`. `searchParams` should be awaited before using its properties. Learn more: https://nextjs.org/docs/messages/sync-dynamic-apis
//     at GamesServerPage (app\(app)\games\page.tsx:62:20)
//   60 |   let targetDate: Date;
//   61 |   // Ensure searchParams is accessed safely within the async context
// > 62 |   const dateParam = searchParams?.date; // Use optional chaining
//      |                    ^
//   63 |
//   64 |   if (typeof dateParam === 'string' && /\d{4}-\d{2}-\d{2}/.test(dateParam)) {
//   65 |      try {

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TeamsHeader } from "@/components/teams/TeamsHeader";
import { TeamCardSkeleton } from "@/components/teams/TeamCardSkeleton";

export default function TeamsLoading() {
  const skeletonCards = Array.from({ length: 8 }, (_, i) => i);

  return (
    <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
      <TeamsHeader />

      <Tabs defaultValue="eastern" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="eastern">Eastern Conference</TabsTrigger>
          <TabsTrigger value="western">Western Conference</TabsTrigger>
        </TabsList>
        
        {/* Eastern Conference Loading State */}
        <TabsContent value="eastern" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {skeletonCards.map((index) => (
              <TeamCardSkeleton key={`eastern-${index}`} />
            ))}
          </div>
        </TabsContent>

        {/* Western Conference Loading State */}
        <TabsContent value="western" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {skeletonCards.map((index) => (
              <TeamCardSkeleton key={`western-${index}`} />
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
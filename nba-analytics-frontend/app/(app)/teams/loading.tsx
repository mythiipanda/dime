import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TeamsHeader } from "@/components/teams/TeamsHeader";
import { TeamTableSkeleton } from "@/components/teams/TeamTable";



export default function TeamsLoading() {
  return (
    <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
      <TeamsHeader />

      <Tabs defaultValue="eastern" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="eastern">Eastern Conference</TabsTrigger>
          <TabsTrigger value="western">Western Conference</TabsTrigger>
        </TabsList>
        
        {/* Use TeamTableSkeleton for both conferences */}
        <TabsContent value="eastern" className="space-y-4">
           <TeamTableSkeleton conference="Eastern" />
        </TabsContent>

        <TabsContent value="western" className="space-y-4">
           <TeamTableSkeleton conference="Western" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
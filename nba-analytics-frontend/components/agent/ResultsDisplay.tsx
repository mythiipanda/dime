// components/agent/ResultsDisplay.tsx
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BotIcon, FileTextIcon, TableIcon, BarChartIcon } from "lucide-react";
import { ErrorDisplay } from "./ErrorDisplay"; // Import ErrorDisplay

interface ResultsDisplayProps {
  isLoading: boolean;
  error: string | null;
  response: string | null;
  resultData: any; // Keep simple for now
}

export function ResultsDisplay({ isLoading, error, response, resultData }: ResultsDisplayProps) {

  // Handle loading state
  if (isLoading && !response && !error) {
    return <Skeleton className="h-64 w-full" />;
  }

  // Handle error state (using the dedicated component)
  if (!isLoading && error) {
    return <ErrorDisplay error={error} />;
  }

  // Handle successful response (potentially with structured data)
  if (!isLoading && !error && (response || resultData)) {
    // If we have structured resultData, show tabs
    if (resultData) {
      return (
        <Tabs defaultValue="summary" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="summary"><FileTextIcon className="mr-1 h-4 w-4" />Summary</TabsTrigger>
            <TabsTrigger value="table" disabled={resultData.type !== 'table'}><TableIcon className="mr-1 h-4 w-4" />Table</TabsTrigger>
            <TabsTrigger value="chart" disabled={resultData.type !== 'chart'}><BarChartIcon className="mr-1 h-4 w-4" />Chart</TabsTrigger>
          </TabsList>
          <TabsContent value="summary">
            <Card>
              <CardHeader>
                <CardTitle>Result Summary</CardTitle>
                <CardDescription>Summary based on agent analysis.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {response || "Summary placeholder..."} {/* Use response as fallback */}
                </p>
              </CardContent>
            </Card>
          </TabsContent>
          {/* Table Content */}
          <TabsContent value="table">
            <Card>
              <CardHeader>
                <CardTitle>Tabular Data</CardTitle>
                <CardDescription>Detailed data in table format.</CardDescription>
              </CardHeader>
              <CardContent>
                {resultData?.type === 'table' && resultData.data?.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {Object.keys(resultData.data[0] || {}).map(key => <TableHead key={key}>{key}</TableHead>)}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {resultData.data.map((row: any, index: number) => (
                        <TableRow key={index}>
                          {Object.values(row).map((val: any, i: number) => <TableCell key={i}>{String(val)}</TableCell>)}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : <p className="text-sm text-muted-foreground">No table data available for this response.</p>}
              </CardContent>
            </Card>
          </TabsContent>
          {/* Chart Content */}
          <TabsContent value="chart">
            <Card>
              <CardHeader>
                <CardTitle>Chart Visualization</CardTitle>
                <CardDescription>Visual representation of the data.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-96 bg-muted rounded-md flex items-center justify-center">
                  {resultData?.type === 'chart' ? 'Chart Placeholder (Recharts integration needed)' : 'No chart data available for this response.'}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      );
    }

    // If only a text response, show it in a card
    if (response) {
       return (
         <Card className="mb-4">
           <CardHeader>
             <CardTitle className="text-base flex items-center gap-2">
               <BotIcon className="h-5 w-5" /> Agent Response
             </CardTitle>
           </CardHeader>
           <CardContent>
             {/* TODO: Render markdown if response contains it */}
             <p className="text-sm whitespace-pre-wrap">{response}</p>
           </CardContent>
         </Card>
       );
    }
  }

  // Default initial state (before any interaction)
  return (
    <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed shadow-sm p-4">
      <div className="flex flex-col items-center gap-1 text-center">
        <h3 className="text-2xl font-bold tracking-tight">
          Ask the NBA Agent
        </h3>
        <p className="text-sm text-muted-foreground">
          Enter your query below to get started.
        </p>
      </div>
    </div>
  );
}
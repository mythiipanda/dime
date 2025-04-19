'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/button';
import { Lightbulb, Copy, Check, Brain, ChevronDown, ChevronUp, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState, useEffect } from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import StatCard from '@/components/research/StatCard';
import ChartRenderer from '@/components/research/ChartRenderer';

// Define types for parsed data (can be moved to types file later)
interface ParsedStatCard {
  id: string; // Unique ID for rendering
  label: string;
  value: string | number;
  unit?: string;
}

interface ParsedChart {
  id: string; // Unique ID
  type: 'bar' | 'line';
  title: string;
  data: { label: string; value: number }[];
}

interface ResearchReportViewerProps {
  reportContent: string;
  suggestions: string[];
  intermediateSteps?: any[];
  onSuggestionClick: (suggestion: string) => void;
  isLoading: boolean;
}

export default function ResearchReportViewer({ 
  reportContent,
  suggestions,
  intermediateSteps = [],
  onSuggestionClick,
  isLoading
}: ResearchReportViewerProps) {
  const [copied, setCopied] = useState(false);
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);
  
  // State for parsed elements
  const [parsedStatCards, setParsedStatCards] = useState<ParsedStatCard[]>([]);
  const [parsedCharts, setParsedCharts] = useState<ParsedChart[]>([]);
  const [narrativeContent, setNarrativeContent] = useState<string>('');

  // Effect to parse content when reportContent changes
  useEffect(() => {
     if (!reportContent) {
         setParsedStatCards([]);
         setParsedCharts([]);
         setNarrativeContent('');
         return;
     }

     // Regex to match any character including newlines: [\s\S]
     const statCardRegex = /<!--\s*STAT_CARD_DATA\s*({[\s\S]*?})\s*-->/g; 
     const chartRegex = /<!--\s*CHART_DATA\s*({[\s\S]*?})\s*-->/g;
     const extractedStats: ParsedStatCard[] = [];
     const extractedCharts: ParsedChart[] = [];
     let remainingContent = reportContent;

     // Extract Stat Cards
     let match;
     while ((match = statCardRegex.exec(reportContent)) !== null) {
         try {
             const jsonData = JSON.parse(match[1]);
             extractedStats.push({ 
                 id: `stat-${extractedStats.length}`,
                 label: jsonData.label,
                 value: jsonData.value,
                 unit: jsonData.unit 
             });
             // Remove the comment from the main content
             remainingContent = remainingContent.replace(match[0], '');
         } catch (e) {
             console.error("Failed to parse StatCard JSON from comment:", match[1], e);
         }
     }

     // Extract Charts
     while ((match = chartRegex.exec(reportContent)) !== null) {
         try {
             const jsonData = JSON.parse(match[1]);
             // Basic validation/formatting
             const formattedData = jsonData.data?.map((d: any) => ({ 
                  label: String(d.label),
                  value: parseFloat(String(d.value)) 
              })).filter((d: any) => !isNaN(d.value)) || [];

             if (formattedData.length > 0) {
                 extractedCharts.push({
                     id: `chart-${extractedCharts.length}`,
                     type: jsonData.type === 'line' ? 'line' : 'bar',
                     title: jsonData.title || 'Chart',
                     data: formattedData
                 });
                 // Remove the comment from the main content
                 remainingContent = remainingContent.replace(match[0], '');
             }
         } catch (e) {
             console.error("Failed to parse Chart JSON from comment:", match[1], e);
         }
     }

     setParsedStatCards(extractedStats);
     setParsedCharts(extractedCharts);
     // Clean up potentially empty lines left by removed comments
     setNarrativeContent(remainingContent.replace(/^\s*\n/gm, '').trim()); 

 }, [reportContent]); // Re-run parsing when reportContent updates

  const fullReportTextForCopy = reportContent || '';

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy report: ', err);
    }
  };

  const components: any = {
     h1: ({ node, ...props }: { node: any, [key: string]: any }) => <h1 className="text-2xl font-bold mb-4 text-primary border-b pb-2 border-border" {...props} />,
     h2: ({ node, ...props }: { node: any, [key: string]: any }) => <h2 className="text-xl font-semibold mt-8 mb-4 text-foreground border-b pb-2 border-border" {...props} />,
     h3: ({ node, ...props }: { node: any, [key: string]: any }) => <h3 className="text-lg font-semibold mt-6 mb-3 text-foreground/90" {...props} />,
     p: ({ node, ...props }: { node: any, [key: string]: any }) => <p className="mb-4 leading-relaxed text-foreground/80" {...props} />,
     ul: ({ node, ...props }: { node: any, [key: string]: any }) => <ul className="list-disc pl-6 mb-4 space-y-1 text-foreground/80" {...props} />,
     ol: ({ node, ...props }: { node: any, [key: string]: any }) => <ol className="list-decimal pl-6 mb-4 space-y-1 text-foreground/80" {...props} />,
     li: ({ node, ...props }: { node: any, [key: string]: any }) => <li className="mb-1" {...props} />,
     code: ({ node, inline, className, children, ...props }: { node: any, inline: any, className: any, children: any, [key: string]: any }) => {
       const match = /language-(\w+)/.exec(className || '')
       return !inline && match ? (
         <pre className="bg-muted/50 p-3 rounded-md overflow-x-auto my-4 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
           <code className={cn(className, 'text-sm font-mono text-foreground')} {...props}>
             {String(children).replace(/\n$/, '')}
           </code>
         </pre>
       ) : (
         <code className={cn(className, 'bg-muted/50 px-1 py-0.5 rounded text-sm font-mono text-foreground')} {...props}>
           {children}
         </code>
       )
     },
     a: ({ node, ...props }: { node: any, [key: string]: any }) => <a className="text-primary hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
     table: ({ node, ...props }: { node: any, [key: string]: any }) => <div className="my-6 w-full overflow-y-auto"><Table className="w-full" {...props} /></div>,
     thead: ({ node, ...props }: { node: any, [key: string]: any }) => <TableHeader {...props} />,
     tbody: ({ node, ...props }: { node: any, [key: string]: any }) => <TableBody {...props} />,
     tr: ({ node, ...props }: { node: any, [key: string]: any }) => <TableRow {...props} />,
     th: ({ node, ...props }: { node: any, [key: string]: any }) => <TableHead className="font-semibold" {...props} />,
     td: ({ node, ...props }: { node: any, [key: string]: any }) => <TableCell {...props} />,
  };

  const hasIntermediateContent = intermediateSteps && intermediateSteps.length > 0;

  if (isLoading && !reportContent) {
     return (
        <div className="border bg-card text-card-foreground rounded-lg p-6 flex items-center justify-center h-60">
            <Loader2 className="mr-3 h-6 w-6 animate-spin text-primary" />
            <span className="text-muted-foreground">Generating report...</span>
        </div>
     );
  }
  
  if (!isLoading && !reportContent) {
     return (
        <div className="border bg-card text-card-foreground rounded-lg p-6 flex items-center justify-center h-60">
            <span className="text-muted-foreground">Report content will appear here.</span>
        </div>
     );
  }

  return (
    <div className="border bg-card text-card-foreground rounded-lg shadow-lg p-4 md:p-6 relative space-y-6"> 
      {hasIntermediateContent && (
         <Collapsible 
           open={isThinkingExpanded} 
           onOpenChange={setIsThinkingExpanded} 
           className="border border-border rounded-md p-3 bg-muted/50"
         >
             <div className="flex items-center justify-between mb-2"> 
               <div className="flex items-center gap-2"> 
                 <Brain className="h-4 w-4 text-muted-foreground" /> 
                 <span className="text-sm font-medium text-muted-foreground">Thinking Process</span> 
               </div> 
               <CollapsibleTrigger asChild> 
                 <Button variant="ghost" size="sm" className="p-1 h-6 w-6"> 
                   {isThinkingExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />} 
                   <span className="sr-only">Toggle Thinking Process</span>
                 </Button> 
               </CollapsibleTrigger> 
            </div> 
            <CollapsibleContent className="space-y-3 pt-2 border-t border-border/50"> 
               {intermediateSteps.map((step: any, index: number) => (
                 <div key={index} className="text-xs text-muted-foreground flex items-center gap-2">
                    {step.event === "ToolCallStarted" && <Loader2 className="h-3 w-3 animate-spin" />}
                    {step.event === "ToolCallCompleted" && <CheckCircle2 className="h-3 w-3 text-green-600" />}
                    {step.event === "Error" && <XCircle className="h-3 w-3 text-red-600" />}
                    <span>{step.event}:</span>
                    {step.tool_name && <span className="font-mono text-primary/80">{step.tool_name}</span>}
                 </div>
               ))}
            </CollapsibleContent> 
         </Collapsible>
      )}

      {/* Stat Cards Section (NEW) */}
      {parsedStatCards.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 not-prose"> 
              {parsedStatCards.map((card) => (
                  <StatCard key={card.id} label={card.label} value={card.value} unit={card.unit} />
              ))}
          </div>
      )}

      {/* Charts Section (NEW) */}
      {parsedCharts.length > 0 && (
          <div className="space-y-6 not-prose"> 
              {parsedCharts.map((chart) => (
                  <ChartRenderer key={chart.id} type={chart.type} title={chart.title} data={chart.data} />
              ))}
          </div>
      )}

      {/* Narrative Content Section (NEW) */}
      {narrativeContent && (
          <div className='relative pt-6 border-t border-border/50'> 
             {/* Copy Button - Now correctly placed without duplication */}
             {fullReportTextForCopy && (
                 <div className="absolute top-4 right-[-8px]"> {/* Adjust position */} 
                     <TooltipProvider> 
                       <Tooltip> 
                         <TooltipTrigger asChild> 
                           <Button 
                             variant="ghost" 
                             size="icon" 
                             className="h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-muted" 
                             onClick={() => copyToClipboard(fullReportTextForCopy)}
                           > 
                             {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />} 
                           </Button> 
                         </TooltipTrigger> 
                         <TooltipContent> 
                           <p className="text-xs">{copied ? 'Copied!' : 'Copy Full Report'}</p> 
                         </TooltipContent> 
                       </Tooltip> 
                     </TooltipProvider> 
                 </div> 
             )} 
             {/* Render Narrative Markdown */}
             <div className="prose prose-sm md:prose-base prose-neutral dark:prose-invert max-w-none text-card-foreground">
                 <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>
                     {narrativeContent}
                 </ReactMarkdown>
             </div>
          </div>
      )}

      {suggestions.length > 0 && !isLoading && (
         <div className="mt-8 pt-6 border-t border-border">
            <h3 className="flex items-center text-lg font-semibold mb-4 text-foreground">
               <Lightbulb className="w-5 h-5 mr-2 text-yellow-500" />
               Suggested Next Steps
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
               {suggestions.map((s: any, i: number) => ( 
                  <Button
                     key={i}
                     variant="outline"
                     size="sm"
                     className={cn(
                        "text-left justify-start h-auto whitespace-normal",
                        "border-border text-muted-foreground", 
                        "hover:bg-accent hover:text-accent-foreground", 
                        "transition-all duration-150 transform hover:scale-[1.02]"
                     )}
                     onClick={() => onSuggestionClick && onSuggestionClick(s)}
                     disabled={isLoading}
                  >
                     {s}
                  </Button>
               ))}
            </div>
         </div>
      )}
    </div>
  );
} 
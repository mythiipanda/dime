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

// Define type for parsed tables
interface ParsedTable {
  id: string; // Unique ID
  title?: string;
  markdown: string;
}

// Simplify props
interface ResearchReportViewerProps {
  reportContent: string;
}

export default function ResearchReportViewer({ 
  reportContent,
}: ResearchReportViewerProps) {
  const [copied, setCopied] = useState(false);
  
  // State for parsed elements
  const [parsedStatCards, setParsedStatCards] = useState<ParsedStatCard[]>([]);
  const [parsedCharts, setParsedCharts] = useState<ParsedChart[]>([]);
  const [parsedTables, setParsedTables] = useState<ParsedTable[]>([]);
  const [narrativeContent, setNarrativeContent] = useState<string>('');

  // Effect to parse content when reportContent changes
  useEffect(() => {
     if (!reportContent) {
         setParsedStatCards([]);
         setParsedCharts([]);
         setParsedTables([]);
         setNarrativeContent('');
         return;
     }

     // Regex to match any character including newlines: [\s\S]
     const statCardRegex = /<!--\s*STAT_CARD_DATA\s*({[\s\S]*?})\s*-->/g; 
     const chartRegex = /<!--\s*CHART_DATA\s*({[\s\S]*?})\s*-->/g;
     const tableRegex = /<!--\s*TABLE_DATA\s*({[\s\S]*?})\s*-->/g;

     const extractedStats: ParsedStatCard[] = [];
     const extractedCharts: ParsedChart[] = [];
     const extractedTables: ParsedTable[] = [];
     let remainingContent = reportContent;
     let match;

     // Extract Stat Cards
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
             const data = jsonData.data?.map((d: any) => ({ 
                 label: String(d.label ?? ''),
                 value: parseFloat(String(d.value ?? 0))
             })).filter((d: any) => d.label && !isNaN(d.value)) || [];

             if (data.length > 0 && (jsonData.type === 'bar' || jsonData.type === 'line')) {
                 extractedCharts.push({
                     id: `chart-${extractedCharts.length}`,
                     type: jsonData.type,
                     title: jsonData.title || 'Chart',
                     data: data
                 });
                 // Remove the comment from the main content
                 remainingContent = remainingContent.replace(match[0], '');
             } else {
                 console.warn("Skipping chart due to invalid data or type:", jsonData);
             }
         } catch (e) {
             console.error("Failed to parse Chart JSON from comment:", match[1], e);
         }
     }

     // Extract Tables
     while ((match = tableRegex.exec(reportContent)) !== null) {
         try {
             const jsonData = JSON.parse(match[1]);
             if (jsonData.markdown && typeof jsonData.markdown === 'string') {
                 extractedTables.push({
                     id: `table-${extractedTables.length}`,
                     title: jsonData.title,
                     markdown: jsonData.markdown
                 });
                 // Remove the comment from the main content
                 remainingContent = remainingContent.replace(match[0], '');
             } else {
                  console.warn("Skipping table comment due to missing/invalid markdown:", jsonData);
             }
         } catch (e) {
             console.error("Failed to parse Table JSON from comment:", match[1], e);
         }
     }

     setParsedStatCards(extractedStats);
     setParsedCharts(extractedCharts);
     setParsedTables(extractedTables);
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

  return (
    <div className="prose prose-zinc dark:prose-invert max-w-none break-words relative group">
      {/* Add Copy button positioned relative to this container */}
        <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-0 right-0 mt-1 mr-1 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10"
                  onClick={() => copyToClipboard(fullReportTextForCopy)}
                >
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{copied ? 'Copied!' : 'Copy report'}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

      {/* Render Stat Cards */} 
      {parsedStatCards.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 mb-6">
          {parsedStatCards.map((card) => (
            <StatCard key={card.id} label={card.label} value={card.value} unit={card.unit} />
          ))}
        </div>
      )}

      {/* Render Charts */} 
      {parsedCharts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {parsedCharts.map((chart) => (
            <div key={chart.id} className="border rounded-lg p-4 shadow-sm">
              <h4 className="text-md font-semibold mb-2 text-center">{chart.title}</h4>
              <ChartRenderer type={chart.type} data={chart.data} title={chart.title} />
            </div>
          ))}
        </div>
      )}

      {/* Render Narrative Content */} 
      {narrativeContent && (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={components}
          >
            {narrativeContent}
          </ReactMarkdown>
      )}

      {/* Render Tables using ReactMarkdown's table handling */} 
      {parsedTables.map((table) => (
         <div key={table.id} className="mt-6 mb-6">
            {table.title && <h3 className="text-lg font-semibold mb-2 text-foreground/90">{table.title}</h3>}
            <ReactMarkdown
               remarkPlugins={[remarkGfm]}
               components={components}
            >
               {table.markdown}
            </ReactMarkdown>
         </div>
      ))}
    </div>
  );
} 
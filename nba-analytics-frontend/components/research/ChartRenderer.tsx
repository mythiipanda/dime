'use client';

import React from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useTheme } from 'next-themes'; // To adapt colors to theme

interface ChartDataPoint {
  label: string; // Corresponds to name in Recharts
  value: number | string; // Corresponds to the data key (will use 'value')
  // Add other potential keys if needed (e.g., for stacked bars)
}

interface ChartRendererProps {
  type: 'bar' | 'line';
  title: string;
  data: ChartDataPoint[];
  // Add options later if needed (e.g., axis labels, colors)
}

export default function ChartRenderer({ type, title, data }: ChartRendererProps) {
  const { resolvedTheme } = useTheme();
  const isDarkMode = resolvedTheme === 'dark';

  // Convert string values to numbers if possible, otherwise filter them out
  const processedData = data
    .map(item => ({ ...item, value: parseFloat(String(item.value)) }))
    .filter(item => !isNaN(item.value));

  if (!processedData || processedData.length === 0) {
    return (
      <Card className="my-4 border-dashed border-border bg-muted/20">
        <CardHeader>
          <CardTitle className="text-base text-muted-foreground">{title}</CardTitle>
        </CardHeader>
        <CardContent className="text-center text-sm text-muted-foreground h-40 flex items-center justify-center">
          No valid data available for this chart.
        </CardContent>
      </Card>
    );
  }

  // Define theme-aware colors
  const strokeColor = isDarkMode ? 'hsl(var(--foreground))' : 'hsl(var(--foreground))'; // Or use specific colors
  const fillColor = isDarkMode ? 'hsl(var(--primary))' : 'hsl(var(--primary))'; // Bar/Area fill
  const gridColor = isDarkMode ? 'hsl(var(--border))' : 'hsl(var(--border))';
  const tooltipBg = isDarkMode ? 'hsl(var(--popover))' : 'hsl(var(--popover))';
  const tooltipText = isDarkMode ? 'hsl(var(--popover-foreground))' : 'hsl(var(--popover-foreground))';

  return (
    <Card className="my-6 bg-card/80 backdrop-blur-sm border-border/50 overflow-hidden">
      <CardHeader>
        <CardTitle className="text-lg text-center font-medium text-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="h-72 md:h-80 pr-4"> {/* Added padding right for YAxis labels */} 
        <ResponsiveContainer width="100%" height="100%">
          {type === 'bar' ? (
            <BarChart data={processedData} margin={{ top: 5, right: 0, left: -20, bottom: 5 }}> {/* Adjusted left margin */} 
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis 
                dataKey="label" 
                stroke={strokeColor} 
                fontSize={12} 
                tickLine={false} 
                axisLine={false}
                // interval={0} // Show all labels if needed, can make axis crowded
                // angle={-30} // Angle labels if they overlap
                // textAnchor="end" 
              />
              <YAxis 
                stroke={strokeColor} 
                fontSize={12} 
                tickLine={false} 
                axisLine={false} 
                tickFormatter={(value) => `${value}`}
              />
              <Tooltip 
                cursor={{ fill: isDarkMode ? 'hsla(var(--muted), 0.3)' : 'hsla(var(--muted), 0.3)' }}
                contentStyle={{ backgroundColor: tooltipBg, color: tooltipText, borderRadius: '0.5rem', border: `1px solid ${gridColor}` }}
              />
              {/* <Legend /> */} 
              <Bar dataKey="value" fill={fillColor} radius={[4, 4, 0, 0]} />
            </BarChart>
          ) : (
            <LineChart data={processedData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}> {/* Adjusted left margin */} 
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis 
                 dataKey="label" 
                 stroke={strokeColor} 
                 fontSize={12} 
                 tickLine={false} 
                 axisLine={false} 
              />
              <YAxis 
                stroke={strokeColor} 
                fontSize={12} 
                tickLine={false} 
                axisLine={false} 
                tickFormatter={(value) => `${value}`}
              />
              <Tooltip 
                 contentStyle={{ backgroundColor: tooltipBg, color: tooltipText, borderRadius: '0.5rem', border: `1px solid ${gridColor}` }}
              />
              {/* <Legend /> */} 
              <Line type="monotone" dataKey="value" stroke={fillColor} strokeWidth={2} activeDot={{ r: 8 }} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
} 
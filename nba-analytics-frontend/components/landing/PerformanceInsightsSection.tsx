"use client";

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Zap, BarChartBig, BrainCircuit } from 'lucide-react'; // Example icons
import { cn } from "@/lib/utils";

interface InsightCardProps {
  icon: React.ElementType;
  title: string;
  value: string;
  description: string;
  className?: string;
  animationDelay?: string;
}

const InsightCard: React.FC<InsightCardProps> = ({ icon: Icon, title, value, description, className, animationDelay }) => {
  return (
    <Card className={cn(
        `relative overflow-hidden p-6 bg-gray-800/40 backdrop-blur-md border border-white/10 rounded-xl shadow-lg hover:shadow-blue-500/10 transition-all duration-300 transform hover:-translate-y-1`,
        `animate-in fade-in-0 slide-in-from-bottom-4 duration-500`,
        className
        )} 
        style={{ animationDelay }}>
      <CardHeader className="relative z-10 pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-gray-400">{title}</CardTitle>
          <Icon className="h-5 w-5 text-cyan-400" />
        </div>
      </CardHeader>
      <CardContent className="relative z-10">
        <div className="text-4xl font-bold text-white">{value}</div>
        <p className="text-xs text-gray-400 pt-1">{description}</p>
      </CardContent>
    </Card>
  );
};

export function PerformanceInsightsSection() {
  const insights = [
    {
      icon: Zap,
      title: "Real-time AI Processing",
      value: "Live",
      description: "Instantly process live game events for faster, smarter in-game decisions.",
      animationDelay: "100ms",
    },
    {
      icon: BarChartBig,
      title: "Autonomous Data Synthesis",
      value: "1M+",
      description: "Dime autonomously sifts through millions of data points to uncover hidden opportunities.",
      animationDelay: "200ms",
    },
    {
      icon: BrainCircuit,
      title: "Adaptive AI Learning",
      value: "Always On",
      description: "Dime continuously learns, delivering increasingly sharp analysis over time.",
      animationDelay: "300ms",
    },
  ];

  return (
    <section className="py-16 md:py-24 bg-gray-950/70 backdrop-blur-sm">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="text-center mb-12 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white sm:text-4xl">
            Autonomous Intelligence Engine
          </h2>
          <p className="mt-4 text-lg leading-8 text-gray-300 max-w-2xl mx-auto">
            Dime leverages cutting-edge AI to deliver unparalleled speed, depth, and adaptive analysis for your NBA operations.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {insights.map((insight) => (
            <InsightCard
              key={insight.title}
              icon={insight.icon}
              title={insight.title}
              value={insight.value}
              description={insight.description}
              animationDelay={insight.animationDelay}
            />
          ))}
        </div>
      </div>
    </section>
  );
} 
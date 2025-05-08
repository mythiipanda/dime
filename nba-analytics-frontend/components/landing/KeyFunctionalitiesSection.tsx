"use client";

import React from 'react';
import Image from 'next/image';
import { Button } from "@/components/ui/button";
import Link from 'next/link';
import { ArrowRight, BarChart3, BrainCircuit } from 'lucide-react';

// Placeholder for Shot Chart Mockup (Dark Theme)
const ShotChartMockup = () => (
  <div className="w-full h-full bg-gray-800/50 p-4 flex items-center justify-center rounded-lg border border-white/10">
    <svg viewBox="0 0 200 188" className="w-full h-auto max-h-[90%]" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="5" y="5" width="190" height="178" rx="10" stroke="#4b5563" strokeWidth="1" fill="#1f2937"/>
      {/* Lighter hoop/backboard */}
      <circle cx="100" cy="45" r="15" stroke="#9ca3af" strokeWidth="1" />
      <line x1="80" y1="45" x2="120" y2="45" stroke="#9ca3af" strokeWidth="1" />
      {/* Lighter court lines */}
      <line x1="5" y1="94" x2="195" y2="94" stroke="#4b5563" strokeWidth="0.5" />
      <rect x="70" y="5" width="60" height="70" stroke="#4b5563" strokeWidth="0.5" />
      <circle cx="100" cy="75" r="12" stroke="#4b5563" strokeWidth="0.5" />
      <path d="M30 5 C 60 110, 140 110, 170 5" stroke="#4b5563" strokeWidth="1" fill="none"/>
      {/* Brighter shot colors */}
      <circle cx="100" cy="20" r="3" fill="#60a5fa" />
      <circle cx="60" cy="60" r="3" fill="#f87171" />
      <circle cx="140" cy="60" r="3" fill="#60a5fa" />
      <circle cx="40" cy="100" r="3" fill="#f87171" />
      <circle cx="160" cy="100" r="3" fill="#60a5fa" />
    </svg>
  </div>
);

// Placeholder for AI Analysis Mockup (Dark Theme)
const AiAnalysisMockup = () => (
  <div className="w-full h-full bg-gray-800/50 p-6 flex flex-col justify-center items-center rounded-lg space-y-4 border border-white/10">
    <BrainCircuit className="h-12 w-12 text-purple-400 opacity-80 mb-3" />
    <div className="w-4/5 h-4 bg-purple-600/50 rounded-sm"></div>
    <div className="w-3/5 h-4 bg-purple-600/30 rounded-sm"></div>
    <div className="grid grid-cols-3 gap-2 w-4/5">
      <div className="h-8 bg-sky-600/50 rounded-sm"></div>
      <div className="h-8 bg-sky-500/60 rounded-sm"></div>
      <div className="h-8 bg-sky-600/40 rounded-sm"></div>
    </div>
    <p className="text-xs text-gray-400 mt-2">AI Processing...</p>
  </div>
);

interface FunctionalityProps {
  title: string;
  description: string;
  imageUrl?: string;
  imageAlt: string;
  alignImageRight?: boolean;
  ctaLink?: string;
  ctaText?: string;
  animationDelay?: string;
  mockupType?: 'shot-chart' | 'ai-analysis'; // To determine which mockup to show
}

const FunctionalityDetail: React.FC<FunctionalityProps> = ({
  title,
  description,
  imageUrl, // Keep imageUrl for potential future use or if a real image is provided
  imageAlt,
  alignImageRight = false,
  ctaLink,
  ctaText,
  animationDelay,
  mockupType,
}) => {
  return (
    <div className={`grid md:grid-cols-2 gap-8 md:gap-12 items-center animate-in fade-in-0 slide-in-from-bottom-5 duration-500`} style={{ animationDelay }}>
      <div className={`order-2 ${alignImageRight ? 'md:order-2' : 'md:order-1'}`}>
        <h3 className="text-2xl md:text-3xl font-bold text-white mb-4">{title}</h3>
        <p className="text-gray-300 leading-relaxed mb-6">
          {description}
        </p>
        {ctaLink && ctaText && (
          <Button asChild variant="outline" className="border-cyan-400/50 text-cyan-400 hover:bg-cyan-400/10 hover:border-cyan-400/80 group">
            <Link href={ctaLink}>
              {ctaText}
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </Button>
        )}
      </div>
      <div className={`order-1 ${alignImageRight ? 'md:order-1' : 'md:order-2'} mt-8 md:mt-0`}>
        <div className="aspect-[16/10] bg-gray-900/50 backdrop-blur-sm rounded-lg shadow-xl overflow-hidden flex items-center justify-center border border-white/10 p-1">
          {mockupType === 'shot-chart' && <ShotChartMockup />}
          {mockupType === 'ai-analysis' && <AiAnalysisMockup />}
          {!mockupType && imageUrl && (
            <Image src={imageUrl} alt={imageAlt} width={500} height={281} className="object-contain p-4" /> 
          )}
          {!mockupType && !imageUrl && (
            <div className="w-full h-full flex items-center justify-center text-gray-600">
              <BarChart3 className="h-16 w-16" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export function KeyFunctionalitiesSection() {
  const functionalities = [
    {
      title: "Autonomous Shot Chart Analysis & Scouting",
      description: "Delegate the scouting grind. Dime automatically dissects player shooting performance, identifying strengths, weaknesses, hot zones, and optimal court positioning.",
      imageAlt: "Interactive NBA Shot Chart Visualization by Dime AI",
      alignImageRight: false,
      ctaLink: "/shot-charts",
      ctaText: "See AI Shot Analysis",
      animationDelay: "0ms",
      mockupType: "shot-chart" as const,
    },
    {
      title: "AI-Driven Strategy & Forecasting",
      description: "Go beyond basic predictions. Dime simulates trade impacts, forecasts player development trajectories, and provides data-backed strategic options for game planning and roster management.",
      imageAlt: "AI-Powered NBA Game Strategic Briefing by Dime AI",
      alignImageRight: true,
      ctaLink: "/research",
      ctaText: "Explore Strategic AI",
      animationDelay: "200ms",
      mockupType: "ai-analysis" as const,
    },
  ];

  return (
    <section className="py-16 md:py-24 bg-gradient-to-b from-gray-950 to-blue-950/80">
      <div className="container mx-auto max-w-7xl px-4 space-y-16 md:space-y-20">
        <div className="text-center animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white">
                Delegate Key Workflows to Dime
            </h2>
            <p className="mt-4 text-lg leading-8 text-gray-300 max-w-3xl mx-auto">
                Automate complex analysis and gain deeper insights by assigning core tasks to your Dime AI agent. Focus on strategy, let Dime handle the data.
            </p>
        </div>
        {functionalities.map((func, index) => (
          <FunctionalityDetail
            key={index}
            title={func.title}
            description={func.description}
            imageAlt={func.imageAlt}
            alignImageRight={func.alignImageRight}
            ctaLink={func.ctaLink}
            ctaText={func.ctaText}
            animationDelay={func.animationDelay}
            mockupType={func.mockupType}
          />
        ))}
      </div>
    </section>
  );
} 
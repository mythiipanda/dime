"use client";

import React from 'react';
import { MessageSquare, Zap, Terminal } from 'lucide-react'; // Removed unused icons, added Terminal

// Placeholder for AI Chat Mockup
const AiChatMockup = () => (
  <div className="w-full h-full bg-gray-900/60 backdrop-blur-sm p-3 sm:p-4 flex flex-col justify-end rounded-lg space-y-2 border border-white/10 shadow-inner shadow-black/20">
    <div className="flex justify-start">
      <div className="bg-blue-700/80 text-gray-100 text-xs sm:text-sm p-2.5 rounded-lg rounded-bl-sm max-w-[75%] shadow-md">
        Tell me about LeBron&apos;s clutch performance.
      </div>
    </div>
    <div className="flex justify-end">
      <div className="bg-gray-700/70 text-gray-200 text-xs sm:text-sm p-2.5 rounded-lg rounded-br-sm shadow-md max-w-[75%]">
        Analyzing clutch stats for LeBron James...
        <Terminal className="inline-block h-3.5 w-3.5 ml-1.5 text-cyan-400 animate-pulse" />
      </div>
    </div>
     <div className="flex justify-start">
      <div className="bg-blue-700/80 text-gray-100 text-xs sm:text-sm p-2.5 rounded-lg rounded-bl-sm max-w-[75%] shadow-md">
        Compare his 4th quarter stats vs Jokic.
      </div>
    </div>
  </div>
);

// Placeholder for AI Parallel Mockup
const AiParallelMockup = () => (
  <div className="w-full h-full bg-gray-900/60 backdrop-blur-sm p-4 sm:p-6 flex flex-col justify-center items-center rounded-lg space-y-3 border border-white/10 shadow-inner shadow-black/20">
    <Zap className="h-10 w-10 text-purple-400 opacity-90 mb-2" />
    <p className="text-xs font-medium text-gray-300 mb-2">Parallel Task Processing</p>
    <div className="w-full h-3 bg-purple-500/70 rounded-full animate-pulse shadow-sm"></div>
    <div className="w-full h-3 bg-cyan-500/70 rounded-full animate-pulse shadow-sm" style={{animationDelay: '0.1s'}}></div>
    <div className="w-full h-3 bg-purple-500/60 rounded-full animate-pulse shadow-sm" style={{animationDelay: '0.2s'}}></div>
    <div className="w-full h-3 bg-cyan-500/60 rounded-full animate-pulse shadow-sm" style={{animationDelay: '0.3s'}}></div>
  </div>
);

export function CollaborativeAiSection() {
  return (
    // Dark theme background
    <section className="py-16 md:py-24 bg-gray-950"> 
      <div className="container mx-auto max-w-7xl px-4">
        {/* Section 1: Built to Collaborate */}
        <div className="grid md:grid-cols-2 gap-12 items-center mb-16 md:mb-24 animate-in fade-in-0 slide-in-from-left-8 duration-500">
          <div className="order-2 md:order-1">
            {/* Dark theme badge */}
            <span className="inline-flex items-center rounded-full bg-blue-900/50 px-3 py-1 text-sm font-medium text-blue-300 mb-3 ring-1 ring-inset ring-blue-300/20">
              <MessageSquare className="h-5 w-5 mr-1.5" />
              Natural Language Interface
            </span>
            {/* Light text */}
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-4">
              Your Collaborative AI Analyst
            </h2>
            {/* Light text */}
            <p className="text-lg text-gray-300 leading-relaxed">
              Interact with Dime naturally. Ask specific questions, request custom analyses, or provide feedback. Dime understands context, learns your requirements, and presents findings clearly, streamlining your research workflow.
            </p>
          </div>
          <div className="order-1 md:order-2 flex justify-center">
            {/* Dark theme mockup container */}
            <div className="w-full max-w-md h-72 bg-gray-800/40 backdrop-blur-md rounded-xl shadow-2xl border border-white/10 flex items-center justify-center p-0.5 overflow-hidden hover:shadow-blue-500/20 transition-shadow duration-300">
              <AiChatMockup />
            </div>
          </div>
        </div>

        {/* Section 2: Works Tirelessly */}
        <div className="grid md:grid-cols-2 gap-12 items-center animate-in fade-in-0 slide-in-from-right-8 duration-500 delay-150">
          <div className="order-1 md:order-1 flex justify-center">
             {/* Dark theme mockup container */}
             <div className="w-full max-w-md h-72 bg-gray-800/40 backdrop-blur-md rounded-xl shadow-2xl border border-white/10 flex items-center justify-center p-0.5 overflow-hidden hover:shadow-purple-500/20 transition-shadow duration-300">
                <AiParallelMockup />
              </div>
          </div>
          <div className="order-2 md:order-2">
             {/* Dark theme badge */}
             <span className="inline-flex items-center rounded-full bg-purple-900/50 px-3 py-1 text-sm font-medium text-purple-300 mb-3 ring-1 ring-inset ring-purple-300/20">
              <Zap className="h-5 w-5 mr-1.5" />
              High-Throughput Analysis
            </span>
            {/* Light text */}
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-4">
              Scalable AI Power for Deep Insights
            </h2>
            {/* Light text */}
            <p className="text-lg text-gray-300 leading-relaxed">
              Dime leverages multiple AI agents operating in parallel to tackle complex, large-scale analyses efficiently. Delegate simultaneous research tasks and receive comprehensive, interconnected results faster, freeing up your time for high-level strategy.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
} 
"use client";

import React from 'react';
import { Button } from '@/components/ui/button'; // Assuming Button component exists
import Link from 'next/link';
import { ArrowRightIcon } from 'lucide-react'; // Changed ChevronDown to ArrowRightIcon

// Updated MockupComponent to match light-mode theme
const MockupComponent = () => {
  return (
    <div className="relative mt-12 lg:mt-0 lg:col-span-5 animate-in fade-in zoom-in-90 duration-700 delay-400">
      {/* Main Frame - dark theme */}
      <div className="bg-gray-900/70 border border-white/10 rounded-lg shadow-xl backdrop-blur-md">
        {/* Window Controls - macOS style */}
        <div className="flex items-center space-x-1.5 p-3 border-b border-white/10">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          <div className="ml-2 flex-grow h-5 bg-gray-700/50 rounded-sm"></div>
        </div>
        {/* Mock Dashboard Content - dark theme */}
        <div className="p-4">
        <div className="h-60 space-y-3 overflow-hidden">
          {/* Mini Chart Example - brighter colors */}
          <div className="flex items-end space-x-1 h-16">
            <div className="w-4 bg-blue-500 rounded-t-sm h-[40%]"></div>
            <div className="w-4 bg-blue-400 rounded-t-sm h-[60%]"></div>
            <div className="w-4 bg-cyan-400 rounded-t-sm h-[80%]"></div>
            <div className="w-4 bg-blue-400 rounded-t-sm h-[70%]"></div>
            <div className="w-4 bg-blue-500 rounded-t-sm h-[50%]"></div>
            <div className="w-4 bg-cyan-500 rounded-t-sm h-[30%]"></div>
          </div>
          {/* Mini Stat Cards - dark theme */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-800/60 p-2 rounded border border-white/10">
              <div className="h-2 w-1/2 bg-gray-600 rounded-sm mb-1.5"></div>
              <div className="h-3 w-1/3 bg-blue-500 rounded-sm"></div>
            </div>
            <div className="bg-gray-800/60 p-2 rounded border border-white/10">
              <div className="h-2 w-1/2 bg-gray-600 rounded-sm mb-1.5"></div>
              <div className="h-3 w-1/3 bg-blue-500 rounded-sm"></div>
            </div>
          </div>
          {/* Mini Table/List - dark theme */}
          <div className="bg-gray-800/60 p-2 rounded border border-white/10 space-y-1.5">
            <div className="h-2 w-3/4 bg-gray-600 rounded-sm"></div>
            <div className="h-2 w-full bg-gray-700 rounded-sm"></div>
            <div className="h-2 w-5/6 bg-gray-700 rounded-sm"></div>
          </div>
        </div>
        </div>
      </div>
      {/* Decorative elements - adapted for dark */}
      <div className="absolute -top-8 -left-8 w-72 h-72 bg-blue-600/10 rounded-full blur-3xl -z-10"></div>
      <div className="absolute -bottom-8 -right-8 w-72 h-72 bg-purple-600/10 rounded-full blur-3xl -z-10"></div>
    </div>
  );
};

export function HeroSection() {
  return (
    // Remove explicit background, inherit from parent
    <section className="relative pt-24 pb-16 md:pt-32 md:pb-20 lg:pt-40 lg:pb-24 px-4 overflow-hidden">
      {/* Enhanced background - using brighter accents for dark theme */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute top-0 left-0 w-[40rem] h-[40rem] bg-cyan-500/10 rounded-full blur-[120px] -translate-x-1/2 opacity-30 animate-pulse"></div>
        <div className="absolute bottom-0 right-0 w-[50rem] h-[50rem] bg-purple-500/10 rounded-full blur-[150px] translate-x-1/4 translate-y-1/4 opacity-20 animate-pulse animation-delay-2000"></div>
        {/* Adding subtle line accents like reference */}
        <svg className="absolute inset-0 -z-10 h-full w-full stroke-white/10 [mask-image:radial-gradient(100%_100%_at_top_right,white,transparent)]" aria-hidden="true">
          <defs>
            <pattern id="hero-pattern" width="200" height="200" x="50%" y="-1" patternUnits="userSpaceOnUse">
              <path d="M.5 200V.5H200" fill="none" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" strokeWidth="0" fill="url(#hero-pattern)" />
        </svg>
      </div>
      
      <div className="container mx-auto max-w-7xl grid lg:grid-cols-12 gap-10 items-center relative z-10">
        {/* Text Content - ensure light text */}
        <div className="lg:col-span-7 text-center lg:text-left">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-white mb-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
            Dime: Your Autonomous
            {/* Adjusted gradient for better visibility on dark */}
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400 mt-1 md:mt-2">
              NBA Analyst Agent.
            </span>
          </h1>
          <p className="text-lg md:text-xl text-gray-300 mb-10 max-w-2xl mx-auto lg:mx-0 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-200">
            Delegate scouting, draft prep, trade simulations, and game strategy analysis to Dime. Get autonomous insights and data-driven recommendations to manage your team operations effectively.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300">
            <Button 
              asChild
              size="lg"
              // Using bright gradient for dark theme CTA
              className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-semibold shadow-lg hover:shadow-cyan-500/30 transition-all duration-300 transform hover:scale-105"
            >
              <Link href="/dashboard" className="group">
                Activate Your Dime Agent
                <ArrowRightIcon className="ml-2 h-5 w-5 opacity-80 group-hover:translate-x-1 transition-transform duration-200 ease-in-out" />
              </Link>
            </Button>
          </div>
          <p className="text-xs text-gray-400 mt-4 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-350">
            Level up your NBA operations. Free trial available.
          </p>
        </div>
        
        <MockupComponent />
      </div>
    </section>
  );
} 
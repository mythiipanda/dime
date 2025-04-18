"use client";

import React from 'react';
import { Button } from '@/components/ui/button'; // Assuming Button component exists
import Link from 'next/link';
import { ArrowRight, ChevronDown } from 'lucide-react'; // Import icons potentially used

// Updated MockupComponent to hint at dashboard features
const MockupComponent = () => {
  return (
    <div className="relative mt-12 lg:mt-0 lg:col-span-5">
      {/* Main Frame */}
      <div className="bg-[#0F1A1B]/70 border border-white/10 rounded-lg p-3 shadow-xl backdrop-blur-sm">
        {/* Window Controls */}
        <div className="flex items-center space-x-1.5 mb-3 pb-2 border-b border-white/10">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
        </div>
        {/* Mock Dashboard Content */}
        <div className="h-64 space-y-3 overflow-hidden">
          {/* Mini Chart Example */}
          <div className="flex items-end space-x-1 h-16">
            <div className="w-4 bg-[#33FF99]/50 rounded-t-sm h-[40%]"></div>
            <div className="w-4 bg-[#33FF99]/70 rounded-t-sm h-[60%]"></div>
            <div className="w-4 bg-[#99FFCC]/80 rounded-t-sm h-[80%]"></div>
            <div className="w-4 bg-[#33FF99]/70 rounded-t-sm h-[70%]"></div>
            <div className="w-4 bg-[#33FF99]/50 rounded-t-sm h-[50%]"></div>
            <div className="w-4 bg-[#33FF99]/40 rounded-t-sm h-[30%]"></div>
          </div>
          {/* Mini Stat Cards */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-[#1A1C1F]/60 p-2 rounded border border-white/5">
              <div className="h-2 w-1/2 bg-[#A7BEBE]/30 rounded-sm mb-1.5"></div>
              <div className="h-3 w-1/3 bg-[#99FFCC]/60 rounded-sm"></div>
            </div>
             <div className="bg-[#1A1C1F]/60 p-2 rounded border border-white/5">
              <div className="h-2 w-1/2 bg-[#A7BEBE]/30 rounded-sm mb-1.5"></div>
              <div className="h-3 w-1/3 bg-[#99FFCC]/60 rounded-sm"></div>
            </div>
          </div>
           {/* Mini Table/List */}
           <div className="bg-[#1A1C1F]/60 p-2 rounded border border-white/5 space-y-1.5">
             <div className="h-2 w-3/4 bg-[#A7BEBE]/30 rounded-sm"></div>
             <div className="h-2 w-full bg-[#A7BEBE]/20 rounded-sm"></div>
             <div className="h-2 w-5/6 bg-[#A7BEBE]/20 rounded-sm"></div>
           </div>
        </div>
      </div>
      {/* Decorative elements */}
      <div className="absolute -top-10 -left-10 w-72 h-72 bg-[#98FCCF]/5 rounded-full blur-3xl -z-10"></div>
      <div className="absolute -bottom-10 -right-10 w-72 h-72 bg-[#002B2E]/10 rounded-full blur-3xl -z-10"></div>
    </div>
  );
};

export function HeroSection() {
  return (
    <section className="relative py-24 md:py-32 lg:py-40 px-4 overflow-hidden">
      {/* Background elements from Figma (Nodes 11:3543, 11:3586) */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        {/* Glowing Lines Example */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96">
          <div className="absolute inset-0 rounded-full border border-[#99FFCC]/10 animate-[spin_20s_linear_infinite]"></div>
          <div className="absolute inset-10 rounded-full border border-[#99FFCC]/5 opacity-50 animate-[spin_25s_linear_infinite_reverse]"></div>
        </div>
         {/* Abstract Ellipses */}
         <div className="absolute top-0 left-0 w-[50rem] h-[50rem] -translate-x-1/2 -translate-y-1/2">
           <div className="absolute inset-0 bg-[#002B2E]/50 rounded-full opacity-30 blur-3xl"></div>
         </div>
          <div className="absolute bottom-0 right-0 w-[40rem] h-[40rem] translate-x-1/2 translate-y-1/2">
           <div className="absolute inset-0 bg-[#98FCCF]/30 rounded-full opacity-20 blur-3xl"></div>
         </div>
      </div>
      
      <div className="container mx-auto max-w-7xl grid lg:grid-cols-12 gap-10 items-center relative z-10">
        {/* Text Content - Updated for future goals */}
        <div className="lg:col-span-7 text-center lg:text-left">
           {/* Badge remains the same */}
           <div className="inline-flex items-center gap-2 bg-[#1A1C1F] border border-[#2A2C31] rounded-full px-4 py-1 mb-6 text-xs font-medium text-[#D6D8DB]">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#99FFCC] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#33FF99]"></span>
            </span>
             NBA Analysis Reimagined
           </div>

          {/* Updated Heading */} 
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-white mb-6">
            Unlock Deeper NBA Insights.
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-[#99FFCC] to-[#33FF99]">
              Powered by AI.
            </span>
          </h1>
          {/* Updated Paragraph */} 
          <p className="text-lg md:text-xl text-[#A7BEBE] mb-10 max-w-2xl mx-auto lg:mx-0">
            Access real-time data, advanced visualizations, player comparisons, and AI-driven analysis to make smarter decisions, faster.
          </p>
          
          {/* Button Container remains the same */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
            <Button 
              asChild
              size="lg" 
              className="bg-[#99FFCC] text-[#000E0F] hover:bg-opacity-90 font-semibold rounded-full px-8 py-3 shadow-[0px_1px_1px_0px_rgba(0,10,10,0.5),_0px_4px_6px_0px_rgba(0,10,10,0.2),_inset_0px_2px_2px_0px_rgba(255,255,255,0.4),_inset_0px_-3px_5px_0px_rgba(0,14,15,0.4)] transition-all duration-300 group"
            >
              <Link href="/dashboard">
                Get Started For Free
                <ChevronDown className="ml-2 h-5 w-5 text-[#000E0F]/80 group-hover:translate-y-0.5 transition-transform" />
              </Link>
            </Button>
          </div>
           <p className="text-xs text-[#A7BEBE] mt-4">No credit card required</p>
        </div>
        
        <MockupComponent />
      </div>
    </section>
  );
} 
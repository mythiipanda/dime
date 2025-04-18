"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import { Check } from 'lucide-react';

export function VisionSection() {
  return (
    <section id="vision" className="py-32 relative overflow-hidden text-white">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-12 items-center">
          {/* Chat Mockup - Apply new styling */}
          <div className="group relative">
            {/* Glow effect */}
            <div className="absolute -inset-1 bg-gradient-to-br from-[#99FFCC]/20 to-[#33FF99]/20 rounded-xl blur-xl opacity-70 group-hover:opacity-100 transition duration-300"></div>
            {/* Card styling */}
            <div className="relative h-[32rem] bg-[#0F1A1B]/70 backdrop-blur-sm rounded-xl border border-white/10 shadow-xl p-4 flex flex-col overflow-hidden">
              {/* Window Controls - Adjusted colors */}
              <div className="flex items-center mb-4 border-b border-white/15 pb-2">
                <div className="w-3 h-3 bg-red-500 rounded-full mr-1.5"></div>
                <div className="w-3 h-3 bg-yellow-500 rounded-full mr-1.5"></div>
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="ml-auto text-xs font-medium text-[#A7BEBE]">AI Assistant</span>
              </div>
              
              {/* Chat messages area - Adjusted message bubble styles */}
              <div className="flex-1 overflow-y-auto mb-3 space-y-4 pr-1 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent">
                {/* User message */}
                <div className="flex justify-end">
                  <p className="bg-gradient-to-r from-[#33FF99]/80 to-[#99FFCC]/80 text-[#000E0F] font-medium rounded-xl py-2.5 px-4 max-w-[80%] text-sm shadow-md">
                    Compare LeBron James and Michael Jordan's career playoff stats.
                  </p>
                </div>
                
                {/* AI response */}
                <div className="flex">
                  <div className="bg-[#1A1C1F]/80 text-[#E2E3E5] rounded-xl py-3 px-4 max-w-[80%] text-sm shadow-md border border-white/10">
                    Generating comparison table... <br />LeBron: 28.5 PPG, 9.0 RPG, 7.2 APG <br />Jordan: 33.4 PPG, 6.4 RPG, 5.7 APG
                  </div>
                </div>
                
                {/* User message */}
                <div className="flex justify-end">
                  <p className="bg-gradient-to-r from-[#33FF99]/80 to-[#99FFCC]/80 text-[#000E0F] font-medium rounded-xl py-2.5 px-4 max-w-[80%] text-sm shadow-md">
                    Show me Steph Curry's shot chart from the 2022 finals.
                  </p>
                </div>
                
                {/* AI response */} 
                <div className="flex">
                  <div className="bg-[#1A1C1F]/80 text-[#E2E3E5] rounded-xl py-3 px-4 max-w-[80%] text-sm shadow-md border border-white/10">
                    Fetching shot chart data and generating visualization...
                  </div>
                </div>
              </div>
              
              {/* Input area - Adjusted styling */}
              <div className="mt-auto flex items-center border-t border-white/15 pt-3">
                <input type="text" placeholder="Ask Dime AI..." className="flex-1 border border-white/10 bg-[#0A1415]/70 text-white rounded-lg py-2 px-4 text-sm focus:outline-none focus:ring-1 focus:ring-[#99FFCC]/50 focus:border-[#99FFCC]/50 placeholder-[#A7BEBE]" />
                <Button size="sm" className="ml-2 bg-[#99FFCC] text-[#000E0F] hover:bg-opacity-90 font-semibold text-xs px-4 py-2 h-auto rounded-lg">
                  Send
                </Button>
              </div>
            </div>
          </div>
          
          {/* Text Content - Updated text */}
          <div className="relative z-10 text-center md:text-left">
            {/* Badge */}
            <div className="inline-flex items-center rounded-full px-4 py-1 mb-5 text-xs font-medium bg-[#1A1C1F] border border-[#2A2C31] text-[#99FFCC] self-start">
              <span>AI Research Assistant</span>
            </div>
            
            <h2 className="text-4xl font-bold text-white mb-6">
              Ask Anything, Get <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#99FFCC] to-[#33FF99]">Instant Answers</span>
            </h2>
            
            <p className="text-lg text-[#A7BEBE] mb-8">
              Leverage our AI assistant trained on comprehensive NBA data. Ask complex questions in natural language and get instant stats, comparisons, visualizations, and analysis.
            </p>
            
            {/* Feature list - Updated text */}
            <ul className="mb-10 space-y-4 text-left max-w-md mx-auto md:mx-0">
              <li className="flex items-start">
                 <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-[#1A1C1F]/50 border border-white/10 rounded-full mr-3 mt-1">
                   <Check className="h-3 w-3 text-[#99FFCC]" />
                 </div>
                <span className="text-[#A7BEBE]">Complex query understanding</span>
              </li>
              <li className="flex items-start">
                <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-[#1A1C1F]/50 border border-white/10 rounded-full mr-3 mt-1">
                  <Check className="h-3 w-3 text-[#99FFCC]" />
                </div>
                <span className="text-[#A7BEBE]">Access to historical & live data</span>
              </li>
              <li className="flex items-start">
                <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-[#1A1C1F]/50 border border-white/10 rounded-full mr-3 mt-1">
                  <Check className="h-3 w-3 text-[#99FFCC]" />
                </div>
                <span className="text-[#A7BEBE]">On-demand charts & tables</span>
              </li>
            </ul>
            
            {/* Call to Action Buttons - Apply new primary style */}
            <div className="flex justify-center md:justify-start">
              <SignedIn>
                <Link href="/dashboard">
                  <Button className="px-8 py-3 text-base font-semibold bg-[#99FFCC] text-[#000E0F] hover:bg-opacity-90 shadow-lg transition-all duration-300 rounded-full">
                    Try the AI Assistant
                  </Button>
                </Link>
              </SignedIn>
              <SignedOut>
                <SignInButton mode="modal">
                  <Button className="px-8 py-3 text-base font-semibold bg-[#99FFCC] text-[#000E0F] hover:bg-opacity-90 shadow-lg transition-all duration-300 rounded-full">
                    Try the AI Assistant
                  </Button>
                </SignInButton>
              </SignedOut>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
} 
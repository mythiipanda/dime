"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";

export function VisionSection() {
  return (
    <section id="vision" className="py-32 sm:py-40 bg-gradient-to-br from-gray-800 to-blue-900 relative overflow-hidden text-white">
      {/* Subtle background decoration */}
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-gray-900 to-gray-800 -z-10"></div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-16 items-center">
        {/* Chat Mockup */}
        <div className="relative w-full h-96 bg-gradient-to-br from-gray-800 to-gray-900 rounded-2xl border border-gray-600 shadow-xl p-6 flex flex-col backdrop-blur-sm transform transition-all duration-500 hover:scale-105 hover:shadow-2xl overflow-hidden">
          {/* Subtle gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-blue-900/20 rounded-2xl pointer-events-none"></div>
          <div className="flex items-center mb-5 border-b border-gray-700 pb-3">
            <div className="w-3 h-3 bg-red-500 rounded-full mr-1.5"></div>
            <div className="w-3 h-3 bg-yellow-500 rounded-full mr-1.5"></div>
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span className="ml-auto text-xs font-medium text-gray-500">AI Assistant</span>
          </div>
          <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-2 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
            <div className="flex justify-end">
              <p className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg py-2 px-3 max-w-xs text-sm shadow-lg">Analyze the Lakers' last 10 games trends in PPG, RPG, FG%, 3P%, and FT%.</p>
            </div>
            <div className="flex">
              <p className="bg-gray-700 text-gray-100 rounded-lg py-3 px-4 max-w-xs text-sm shadow-lg transition-all duration-300">Sure! Summary:<br />
                <strong>PPG:</strong> 27.1 avg<br />
                <strong>RPG:</strong> 7.4 avg<br />
                <strong>FG% trend:</strong> 48.5% → 52.8%<br />
                <strong>3P% trend:</strong> 36.2% → 39.0%<br />
                <strong>FT% trend:</strong> 78.4% → 85.2%</p>
            </div>
            <div className="flex justify-end">
              <p className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg py-2 px-3 max-w-xs text-sm shadow-lg">Generate a line chart visualization for these metrics.</p>
            </div>
            <div className="flex">
              <p className="bg-gray-700 text-gray-100 rounded-lg py-3 px-4 max-w-xs text-sm shadow-lg transition-all duration-300">Here's your line chart visualization.</p>
            </div>
          </div>
          <div className="mt-auto flex items-center border-t border-gray-700 pt-3">
            <input type="text" placeholder="Ask Dime AI..." className="flex-1 border border-gray-600 bg-gray-800 text-white rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent" />
            <Button size="sm" className="ml-2 bg-blue-500 text-white hover:bg-blue-600 transition-all duration-300">
              Send
            </Button>
          </div>
        </div>
        {/* Text Content */}
        <div className="relative z-10">
          <div className="inline-flex items-center rounded-full px-5 py-2 mb-6 text-sm font-medium bg-blue-500/30 text-blue-200 ring-1 ring-inset ring-blue-400 self-start">
            <span>AI Research Assistant</span>
          </div>
          <h2 className="text-4xl font-bold text-white mb-6">Your AI NBA <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">Research Partner</span></h2>
          <p className="text-xl text-gray-200 mb-10">Go beyond basic stats. Ask natural-language questions to instantly get charts, detailed tables, and source references for unparalleled NBA insights.</p>
          <ul className="mb-10 space-y-4">
            <li className="flex items-start">
              <svg className="h-6 w-6 text-blue-400 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-200 text-lg">Real-time data analysis</span>
            </li>
            <li className="flex items-start">
              <svg className="h-6 w-6 text-blue-400 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-200 text-lg">Natural language queries</span>
            </li>
            <li className="flex items-start">
              <svg className="h-6 w-6 text-blue-400 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-200 text-lg">Visual data representation</span>
            </li>
          </ul>
          <SignedIn>
            <Link href="/dashboard"><Button className="px-8 py-4 text-base font-semibold bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg hover:from-blue-600 hover:to-cyan-600 transition-all duration-300 rounded-lg">Try the AI Assistant</Button></Link>
          </SignedIn>
          <SignedOut>
            <SignInButton mode="modal">
              <Button className="px-8 py-4 text-base font-semibold bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg hover:from-blue-600 hover:to-cyan-600 transition-all duration-300 rounded-lg">Try the AI Assistant</Button>
            </SignInButton>
          </SignedOut>
        </div>
      </div>
    </section>
  );
} 
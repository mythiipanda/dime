"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";

export function VisionSection() {
  return (
    <section id="vision" className="py-24 sm:py-32 bg-white relative overflow-hidden">
      {/* Subtle background decoration */}
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-slate-50 to-white -z-10"></div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-16 items-center">
        {/* Chat Mockup */}
        <div className="relative w-full h-96 bg-white rounded-2xl shadow-2xl p-6 flex flex-col border border-gray-200 transform transition-transform hover:scale-[1.02] duration-300 hover:shadow-blue-100">
          {/* Subtle gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-50/30 to-white rounded-2xl pointer-events-none"></div>
          <div className="flex items-center mb-4 border-b pb-3">
            <div className="w-3 h-3 bg-red-500 rounded-full mr-1.5"></div>
            <div className="w-3 h-3 bg-yellow-500 rounded-full mr-1.5"></div>
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span className="ml-auto text-xs font-medium text-gray-500">AI Assistant</span>
          </div>
          <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-2 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
            <div className="flex justify-end">
              <p className="bg-blue-600 text-white rounded-lg py-2 px-3 max-w-xs text-sm shadow">Show me LeBron James's season stats compared to last year.</p>
            </div>
            <div className="flex">
              <p className="bg-gray-200 text-gray-800 rounded-lg py-2 px-3 max-w-xs text-sm shadow">Sure! Here's the comparison:<br />
                <strong>This Year:</strong> 27.1 PPG, 7.4 RPG, 7.4 APG<br />
                <strong>Last Year:</strong> 28.9 PPG, 8.3 RPG, 6.8 APG
              </p>
            </div>
            <div className="flex justify-end">
              <p className="bg-blue-600 text-white rounded-lg py-2 px-3 max-w-xs text-sm shadow">Thanks!</p>
            </div>
          </div>
          <div className="mt-auto flex items-center border-t pt-3">
            <input type="text" placeholder="Ask Dime AI..." className="flex-1 border border-gray-300 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent" />
            <Button size="sm" className="ml-2 bg-blue-600 text-white hover:bg-blue-700">
              Send
            </Button>
          </div>
        </div>
        {/* Text Content */}
        <div className="relative z-10">
          <div className="inline-flex items-center rounded-full px-3 py-1 mb-4 text-sm font-medium bg-blue-50 text-blue-600 ring-1 ring-inset ring-blue-500/20 self-start">
            <span>AI Research Assistant</span>
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Your AI NBA <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Research Partner</span></h2>
          <p className="text-lg text-gray-600 mb-8">Go beyond basic stats. Ask natural-language questions to instantly get charts, detailed tables, and source references for unparalleled NBA insights.</p>
          <ul className="mb-8 space-y-2">
            <li className="flex items-start">
              <svg className="h-5 w-5 text-blue-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-700">Real-time data analysis</span>
            </li>
            <li className="flex items-start">
              <svg className="h-5 w-5 text-blue-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-700">Natural language queries</span>
            </li>
            <li className="flex items-start">
              <svg className="h-5 w-5 text-blue-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-700">Visual data representation</span>
            </li>
          </ul>
          <SignedIn>
            <Link href="/dashboard"><Button className="px-6 py-2.5 text-base font-semibold bg-blue-600 text-white shadow-sm hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">Try the AI Assistant</Button></Link>
          </SignedIn>
          <SignedOut>
            <SignInButton mode="modal">
              <Button className="px-6 py-2.5 text-base font-semibold bg-blue-600 text-white shadow-sm hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">Try the AI Assistant</Button>
            </SignInButton>
          </SignedOut>
        </div>
      </div>
    </section>
  );
} 
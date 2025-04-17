"use client";

import Link from 'next/link';
import React from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import { Check, ChartBar, Trophy, TrendingUp, Users } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="relative flex flex-col min-h-screen bg-white text-gray-900 overflow-hidden">
      {/* Navbar */}
      <header className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-sm shadow-sm">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold text-gray-900">Dime</Link>
          <div className="hidden md:flex items-center space-x-8">
            <Link href="#features" className="hover:text-gray-600">Features</Link>
            <Link href="#vision" className="hover:text-gray-600">Vision</Link>
            <Link href="#pricing" className="hover:text-gray-600">Pricing</Link>
          </div>
          <div className="flex space-x-4">
            <SignedIn>
              <Link href="/dashboard"><Button variant="outline">Dashboard</Button></Link>
            </SignedIn>
            <SignedOut>
              <SignInButton mode="modal" afterSignInUrl="/dashboard" afterSignUpUrl="/dashboard">
                <Button variant="outline">Sign in</Button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <Link href="/dashboard"><Button className="bg-gradient-to-r from-purple-500 to-blue-400 text-white hover:opacity-90">Check demo</Button></Link>
            </SignedIn>
            <SignedOut>
              <SignInButton mode="modal" afterSignInUrl="/dashboard" afterSignUpUrl="/dashboard">
                <Button className="bg-gradient-to-r from-purple-500 to-blue-400 text-white hover:opacity-90">Check demo</Button>
              </SignInButton>
            </SignedOut>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-20 flex-auto">
        {/* Hero - Enhanced Styling */}
        <section className="relative isolate overflow-hidden pt-28 pb-20 sm:pt-36">
          {/* Gradient Background Shapes */}
          <div className="absolute inset-0 -z-10 overflow-hidden">
            <svg
              className="absolute left-[max(50%,25rem)] top-0 h-[64rem] w-[128rem] -translate-x-1/2 stroke-gray-200 [mask-image:radial-gradient(64rem_64rem_at_top,white,transparent)]"
              aria-hidden="true"
            >
              <defs>
                <pattern
                  id="e813992c-7d03-4cc4-a2bd-151760b470a0"
                  width={200}
                  height={200}
                  x="50%"
                  y={-1}
                  patternUnits="userSpaceOnUse"
                >
                  <path d="M100 200V.5M.5 .5H200" fill="none" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" strokeWidth={0} fill="url(#e813992c-7d03-4cc4-a2bd-151760b470a0)" />
            </svg>
            <div className="absolute -top-52 left-1/2 -z-10 -translate-x-1/2 transform-gpu blur-3xl sm:top-[-28rem] sm:ml-16 sm:translate-x-0 sm:transform-gpu" aria-hidden="true">
              <div className="aspect-[1097/845] w-[68.5625rem] bg-gradient-to-tr from-[#8b5cf6] to-[#3b82f6] opacity-20" style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
            </div>
            <div className="absolute -top-52 right-1/2 -z-10 translate-x-1/2 transform-gpu blur-3xl sm:top-[-28rem] sm:mr-16 sm:translate-x-0 sm:transform-gpu" aria-hidden="true">
              <div className="aspect-[1097/845] w-[68.5625rem] bg-gradient-to-tl from-[#3b82f6] to-[#8b5cf6] opacity-20" style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
            </div>
          </div>

          <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-16 items-center">
            <div className="relative z-10">
              <h1 className="text-5xl font-extrabold tracking-tight text-gray-900 sm:text-6xl lg:text-7xl mb-6">NBA Insights, <br /> Elevated</h1>
              <p className="text-lg leading-8 text-gray-600 mb-8">Discover trends, analyze player performance, and get AI-driven game previews faster than ever. Unlock the future of basketball analytics.</p>
              <SignedIn>
                <Link href="/dashboard"><Button size="lg" className="px-8 py-3 text-base font-semibold bg-gradient-to-r from-purple-600 to-blue-500 text-white shadow-sm hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">Check Demo</Button></Link>
              </SignedIn>
              <SignedOut>
                <SignInButton mode="modal" afterSignInUrl="/dashboard" afterSignUpUrl="/dashboard">
                  <Button size="lg" className="px-8 py-3 text-base font-semibold bg-gradient-to-r from-purple-600 to-blue-500 text-white shadow-sm hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">Check Demo</Button>
                </SignInButton>
              </SignedOut>
            </div>

            {/* Enhanced Mockup Section */}
            <div className="relative mt-16 h-80 lg:mt-8 xl:mt-12">
              <div className="absolute inset-0 w-full h-full bg-gradient-to-br from-purple-100 to-blue-100 rounded-xl shadow-xl p-6 overflow-hidden transform transition-transform hover:scale-105 duration-300">
                <div className="grid grid-cols-2 grid-rows-2 gap-4 h-full">
                  <Card className="p-4 bg-white/80 backdrop-blur-sm rounded-lg shadow-md">
                    <p className="text-xs font-medium text-gray-500">Active Players</p>
                    <p className="text-xl font-bold text-gray-800">450+</p>
                  </Card>
                  <Card className="p-4 bg-white/80 backdrop-blur-sm rounded-lg shadow-md">
                    <p className="text-xs font-medium text-gray-500">Games Tracked</p>
                    <p className="text-xl font-bold text-gray-800">1,230</p>
                  </Card>
                  <Card className="p-4 bg-white/80 backdrop-blur-sm rounded-lg shadow-md">
                    <p className="text-xs font-medium text-gray-500">Teams Covered</p>
                    <p className="text-xl font-bold text-gray-800">30</p>
                  </Card>
                  <Card className="p-4 bg-white/80 backdrop-blur-sm rounded-lg shadow-md">
                    <p className="text-xs font-medium text-gray-500">Data Points</p>
                    <p className="text-xl font-bold text-gray-800">1M+</p>
                  </Card>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Future Features */}
        <section id="features" className="bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center mb-16">
            <h2 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl mb-4">Future-Ready AI Features</h2>
            <p className="text-lg leading-8 text-gray-600">Explore what’s next on the horizon for Dime.</p>
          </div>
          <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {/* Feature Card 1 */}
            <Card className="p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col items-start text-left">
              <div className="p-2 bg-blue-100 rounded-lg mb-4">
                <ChartBar className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Game Summaries</h3>
              <p className="text-sm text-gray-600 leading-relaxed">Auto-generated recaps identifying key moments, stats, and turning points.</p>
            </Card>
            {/* Feature Card 2 */}
            <Card className="p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col items-start text-left">
              <div className="p-2 bg-purple-100 rounded-lg mb-4">
                <Users className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Player Comparisons</h3>
              <p className="text-sm text-gray-600 leading-relaxed">Dynamic side-by-side performance analysis across multiple seasons or games.</p>
            </Card>
            {/* Feature Card 3 */}
            <Card className="p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col items-start text-left">
              <div className="p-2 bg-green-100 rounded-lg mb-4">
                <TrendingUp className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Trend Detection</h3>
              <p className="text-sm text-gray-600 leading-relaxed">AI spots emerging player performance shifts and team tendencies before they become obvious.</p>
            </Card>
            {/* Feature Card 4 */}
            <Card className="p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col items-start text-left">
              <div className="p-2 bg-yellow-100 rounded-lg mb-4">
                <Trophy className="h-6 w-6 text-yellow-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Predictive Insights</h3>
              <p className="text-sm text-gray-600 leading-relaxed">Leverage historical data and AI models for game outcome and player impact predictions.</p>
            </Card>
          </div>
        </section>

        {/* AI Assistant Vision - Enhanced Styling */}
        <section id="vision" className="py-20 bg-gray-50">
          <div className="mx-auto max-w-7xl px-6 grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-16 items-center">
            {/* Enhanced Chat Mockup */}
            <div className="relative w-full h-96 bg-white rounded-xl shadow-xl p-6 flex flex-col border border-gray-200 transform transition-transform hover:scale-105 duration-300">
              <div className="flex items-center mb-4 border-b pb-3">
                <div className="w-3 h-3 bg-red-500 rounded-full mr-1.5"></div>
                <div className="w-3 h-3 bg-yellow-500 rounded-full mr-1.5"></div>
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="ml-auto text-xs font-medium text-gray-500">AI Assistant</span>
              </div>
              <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-2 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
                <div className="flex justify-end">
                  <p className="bg-blue-500 text-white rounded-lg py-2 px-3 max-w-xs text-sm shadow">Show me LeBron James's season stats compared to last year.</p>
                </div>
                <div className="flex">
                  <p className="bg-gray-200 text-gray-800 rounded-lg py-2 px-3 max-w-xs text-sm shadow">Sure! Here's the comparison:<br/>
                    <strong>This Year:</strong> 27.1 PPG, 7.4 RPG, 7.4 APG<br/>
                    <strong>Last Year:</strong> 28.9 PPG, 8.3 RPG, 6.8 APG
                  </p>
                </div>
                <div className="flex justify-end">
                  <p className="bg-blue-500 text-white rounded-lg py-2 px-3 max-w-xs text-sm shadow">Thanks!</p>
                </div>
              </div>
              <div className="mt-auto flex items-center border-t pt-3">
                <input type="text" placeholder="Ask Dime AI..." className="flex-1 border border-gray-300 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent" />
                <Button size="sm" className="ml-2 bg-gradient-to-r from-purple-500 to-blue-400 text-white hover:opacity-90">
                  Send
                </Button>
              </div>
            </div>
            <div className="relative z-10">
              <h2 className="text-3xl font-bold mb-4">Your AI NBA Research Partner</h2>
              <p className="text-lg text-gray-600 mb-8">Go beyond basic stats. Ask natural-language questions to instantly get charts, detailed tables, and source references for unparalleled NBA insights.</p>
              <SignedIn>
                <Link href="/dashboard"><Button className="px-6 py-2.5 text-base font-semibold bg-gradient-to-r from-purple-500 to-blue-400 text-white shadow-sm hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500">Try the AI Assistant</Button></Link>
              </SignedIn>
              <SignedOut>
                <SignInButton mode="modal" afterSignInUrl="/dashboard" afterSignUpUrl="/dashboard">
                  <Button className="px-6 py-2.5 text-base font-semibold bg-gradient-to-r from-purple-500 to-blue-400 text-white shadow-sm hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500">Try the AI Assistant</Button>
                </SignInButton>
              </SignedOut>
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="bg-gradient-to-b from-gray-50 to-white py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center mb-16">
            <h2 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl mb-4">Flexible Pricing</h2>
            <p className="text-lg leading-8 text-gray-600">Choose the plan that scales with your analysis needs.</p>
          </div>
          <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Placeholder Pricing Card 1 */}
            <Card className="p-8 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Hobbyist</h3>
              <p className="text-4xl font-bold text-gray-900 mb-4">$9<span className="text-base font-medium text-gray-500">/mo</span></p>
              <ul className="text-sm text-gray-600 space-y-2 mb-6 text-left list-disc list-inside">
                <li>Basic Stats Access</li>
                <li>Limited AI Queries</li>
                <li>Community Support</li>
              </ul>
              <Button variant="outline" className="mt-auto">Get Started</Button>
            </Card>
            {/* Placeholder Pricing Card 2 (Featured) */}
            <Card className="p-8 rounded-xl border-2 border-blue-500 shadow-lg relative flex flex-col text-center scale-105">
              <div className="absolute top-0 right-0 -mt-3 mr-3 bg-blue-500 text-white text-xs font-semibold px-2 py-1 rounded-full">Most Popular</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Pro</h3>
              <p className="text-4xl font-bold text-gray-900 mb-4">$29<span className="text-base font-medium text-gray-500">/mo</span></p>
              <ul className="text-sm text-gray-600 space-y-2 mb-6 text-left list-disc list-inside">
                <li>Full Stats Access</li>
                <li>Advanced AI Queries</li>
                <li>Player Comparisons</li>
                <li>Trend Detection</li>
                <li>Priority Support</li>
              </ul>
              <Button className="mt-auto bg-gradient-to-r from-purple-500 to-blue-400 text-white hover:opacity-90">Choose Pro</Button>
            </Card>
            {/* Placeholder Pricing Card 3 */}
            <Card className="p-8 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Enterprise</h3>
              <p className="text-4xl font-bold text-gray-900 mb-4">Custom</p>
              <ul className="text-sm text-gray-600 space-y-2 mb-6 text-left list-disc list-inside">
                <li>API Access</li>
                <li>Custom Models</li>
                <li>Dedicated Support</li>
              </ul>
              <Button variant="outline" className="mt-auto">Contact Us</Button>
            </Card>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 py-12 text-gray-400">
        <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row justify-between items-center">
          <div className="mb-8 md:mb-0 text-center md:text-left">
            <h3 className="text-xl font-bold text-white mb-2">Dime</h3>
            <p className="text-sm">Empowering NBA analysis through AI.</p>
            <p className="text-xs mt-4">&copy; {new Date().getFullYear()} Dime Analytics. All rights reserved.</p>
          </div>
          <div className="flex space-x-8 text-sm">
            <Link href="#features" className="hover:text-white">Features</Link>
            <Link href="#vision" className="hover:text-white">Vision</Link>
            <Link href="#pricing" className="hover:text-white">Pricing</Link>
            <SignedIn>
              <Link href="/dashboard" className="hover:text-white">Dashboard</Link>
            </SignedIn>
            <SignedOut>
              <SignInButton mode="modal" afterSignInUrl="/dashboard" afterSignUpUrl="/dashboard">
                <span className="hover:text-white cursor-pointer">Sign in</span>
              </SignInButton>
            </SignedOut>
          </div>
        </div>
      </footer>
    </div>
  );
}

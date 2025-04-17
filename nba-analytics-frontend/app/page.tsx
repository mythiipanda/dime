"use client";

import Link from 'next/link';
import Image from 'next/image';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Navbar } from '@/components/ui/navbar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowRight, BarChart3, Zap, Search, Check, Trophy, Database, Users, ChevronRight } from 'lucide-react';

export default function Home() {
  const [activeTab, setActiveTab] = useState('features');
  
  return (
    <div className="relative min-h-screen bg-white text-gray-900 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden">
        <div className="absolute top-[-10%] right-[-5%] w-[600px] h-[600px] opacity-10">
          <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
            <path fill="#0066FF" d="M44.7,-76.4C58.8,-69.2,71.8,-59.1,79.6,-45.8C87.4,-32.6,90,-16.3,88.5,-1.5C87,13.3,81.3,26.6,73.6,39.1C65.9,51.6,56.1,63.3,43.4,70.3C30.7,77.2,15.3,79.3,0.7,78.2C-13.9,77.1,-27.8,72.8,-41.2,66.2C-54.6,59.6,-67.5,50.8,-76.7,38.7C-85.9,26.6,-91.4,13.3,-89.9,0.9C-88.3,-11.5,-79.8,-23.1,-72.3,-35.8C-64.8,-48.5,-58.3,-62.4,-47.1,-71.3C-35.9,-80.3,-20,-84.3,-3.9,-78.4C12.2,-72.5,30.5,-83.5,44.7,-76.4Z" transform="translate(100 100)" />
          </svg>
        </div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] opacity-5">
          <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
            <path fill="#0066FF" d="M36.8,-64.5C50.3,-56.3,65.8,-50.5,73.7,-39.5C81.7,-28.4,82.1,-12.2,81.2,3.5C80.2,19.3,77.8,34.5,71.6,51.8C65.5,69.2,55.5,88.7,41.3,96.5C27.2,104.2,8.8,100.4,-8.1,93.8C-25,87.2,-40.5,77.8,-52.5,65.8C-64.5,53.9,-73,39.3,-81.4,22.5C-89.8,5.7,-98.2,-13.2,-95.3,-30.2C-92.3,-47.1,-78,-61.9,-61.6,-69.9C-45.2,-77.9,-26.6,-78.9,-10.3,-74.4C6,-69.8,23.3,-72.7,36.8,-64.5Z" transform="translate(100 100)" />
          </svg>
        </div>
      </div>

      {/* Navbar */}
      <header className="fixed w-full z-50 bg-white shadow-sm">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center gap-2">
              <div className="rounded-lg bg-blue-600 p-2">
                <BarChart3 className="h-5 w-5 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Dime</span>
            </Link>
            
            <nav className="hidden md:flex items-center space-x-8">
              <Link href="#features" className="text-gray-700 hover:text-blue-600 transition-colors font-medium">
                Features
              </Link>
              <Link href="#demo" className="text-gray-700 hover:text-blue-600 transition-colors font-medium">
                Demo
              </Link>
              <Link href="#pricing" className="text-gray-700 hover:text-blue-600 transition-colors font-medium">
                Pricing
              </Link>
              <Link href="#about" className="text-gray-700 hover:text-blue-600 transition-colors font-medium">
                About
              </Link>
            </nav>
            
            <div className="flex items-center gap-4">
              <Link href="/dashboard">
                <Button variant="outline" className="hidden md:inline-flex border-gray-300 hover:bg-gray-100 text-gray-900">
                  Sign In
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button className="bg-blue-600 hover:bg-blue-700 text-white">
                  Try Demo
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 pt-16">
        {/* Hero Section */}
        <section className="pt-24 pb-20">
          <div className="container mx-auto px-4">
            <div className="flex flex-col md:flex-row items-center gap-12">
              <div className="md:w-1/2 space-y-6">
                <div className="inline-flex items-center px-3 py-1 rounded-full bg-blue-100 border border-blue-200">
                  <span className="text-xs font-medium text-blue-700">AI-Powered NBA Analytics</span>
                </div>
                <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight text-gray-900">
                  <span className="text-blue-600">DIME</span>
                  <span className="block">NBA Analytics AI</span>
                </h1>
                <p className="text-lg text-gray-600 max-w-xl">
                  An AI-powered platform that delivers real-time scores, odds, and deep insights for NBA analysts, data scientists, and passionate fans.
                </p>
                <div className="flex flex-col sm:flex-row items-start gap-4">
                  <Link href="/dashboard">
                    <Button size="lg" className="px-8 py-6 text-base bg-blue-600 hover:bg-blue-700 text-white">
                      Try the Demo <ArrowRight className="ml-2 h-5 w-5" />
                    </Button>
                  </Link>
                  <Link href="#features">
                    <Button variant="outline" size="lg" className="px-8 py-6 text-base border-gray-300 bg-white hover:bg-gray-100 text-gray-900">
                      View Features
                    </Button>
                  </Link>
                </div>
                <div className="flex items-center gap-2 pt-4">
                  <div className="flex -space-x-2">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="w-8 h-8 rounded-full bg-gray-300 border-2 border-white flex items-center justify-center text-xs font-bold">
                        {i}
                      </div>
                    ))}
                  </div>
                  <span className="text-sm text-gray-600">Trusted by NBA data professionals worldwide</span>
                </div>
              </div>
              <div className="md:w-1/2 relative h-[400px]">
                <div className="absolute inset-0 flex items-center justify-center overflow-hidden rounded-lg shadow-xl">
                  <Image src="/dashboard-mockup.svg" alt="NBA Dashboard" fill className="object-cover" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section with Tabs */}
        <section id="features" className="py-24 bg-gray-50">
          <div className="container mx-auto px-4">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">Advanced NBA Analytics Features</h2>
              <p className="text-lg text-gray-600">Discover why Dime is transforming how NBA analysts work with data through AI-powered insights.</p>
            </div>
            
            <Tabs defaultValue="scores" className="max-w-4xl mx-auto">
              <TabsList className="grid w-full grid-cols-3 mb-8">
                <TabsTrigger value="scores" className="text-base py-3">Live Scores & Odds</TabsTrigger>
                <TabsTrigger value="analytics" className="text-base py-3">Advanced Analytics</TabsTrigger>
                <TabsTrigger value="ai" className="text-base py-3">AI Assistant</TabsTrigger>
              </TabsList>
              
              <TabsContent value="scores" className="border rounded-xl overflow-hidden shadow-lg">
                <div className="flex flex-col lg:flex-row bg-white overflow-hidden">
                  <div className="lg:w-1/2 p-8 flex flex-col justify-center">
                    <div className="rounded-full bg-blue-100 w-12 h-12 flex items-center justify-center mb-6">
                      <BarChart3 className="h-6 w-6 text-blue-600" />
                    </div>
                    <h3 className="text-2xl font-bold text-gray-900 mb-4">Real-Time Game Tracking</h3>
                    <ul className="space-y-3">
                      {[
                        'Live score updates with minimal delay',
                        'Betting lines from major sportsbooks',
                        'In-game stat tracking for all players',
                        'Historical odds movements and trends'
                      ].map((feature, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <div className="rounded-full bg-green-100 p-1">
                            <Check className="h-4 w-4 text-green-600" />
                          </div>
                          <span className="text-gray-700">{feature}</span>
                        </li>
                      ))}
                    </ul>
                    <Link href="/dashboard" className="mt-6 inline-flex items-center text-blue-600 font-medium">
                      Try the live scores dashboard
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Link>
                  </div>
                  <div className="lg:w-1/2 bg-gray-100 p-4 relative min-h-[320px] flex items-center justify-center">
                    <div className="relative w-full h-full overflow-hidden rounded-lg shadow-inner">
                      <Image src="/nba-court.svg" alt="NBA Court with Statistics" fill className="object-cover" />
                    </div>
                  </div>
                </div>
              </TabsContent>
              
              <TabsContent value="analytics" className="border rounded-xl overflow-hidden shadow-lg">
                <div className="flex flex-col lg:flex-row bg-white overflow-hidden">
                  <div className="lg:w-1/2 p-8 flex flex-col justify-center">
                    <div className="rounded-full bg-blue-100 w-12 h-12 flex items-center justify-center mb-6">
                      <Database className="h-6 w-6 text-blue-600" />
                    </div>
                    <h3 className="text-2xl font-bold text-gray-900 mb-4">Deep Statistical Insights</h3>
                    <ul className="space-y-3">
                      {[
                        'Advanced player and team statistics',
                        'Custom data visualizations and charts',
                        'Performance trend analysis',
                        'Historical statistical comparisons'
                      ].map((feature, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <div className="rounded-full bg-green-100 p-1">
                            <Check className="h-4 w-4 text-green-600" />
                          </div>
                          <span className="text-gray-700">{feature}</span>
                        </li>
                      ))}
                    </ul>
                    <Link href="/dashboard" className="mt-6 inline-flex items-center text-blue-600 font-medium">
                      Explore advanced analytics
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Link>
                  </div>
                  <div className="lg:w-1/2 bg-gray-100 p-4 relative min-h-[320px] flex items-center justify-center">
                    <div className="relative w-full h-full overflow-hidden rounded-lg shadow-inner">
                      <Image src="/stats-icon.svg" alt="Advanced Statistics" width={150} height={150} className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
                    </div>
                  </div>
                </div>
              </TabsContent>
              
              <TabsContent value="ai" className="border rounded-xl overflow-hidden shadow-lg">
                <div className="flex flex-col lg:flex-row bg-white overflow-hidden">
                  <div className="lg:w-1/2 p-8 flex flex-col justify-center">
                    <div className="rounded-full bg-blue-100 w-12 h-12 flex items-center justify-center mb-6">
                      <Search className="h-6 w-6 text-blue-600" />
                    </div>
                    <h3 className="text-2xl font-bold text-gray-900 mb-4">AI-Powered Research Assistant</h3>
                    <ul className="space-y-3">
                      {[
                        'Natural language query processing',
                        'Data-backed answers to complex questions',
                        'Historical record search and synthesis',
                        'Correlation and trend identification'
                      ].map((feature, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <div className="rounded-full bg-green-100 p-1">
                            <Check className="h-4 w-4 text-green-600" />
                          </div>
                          <span className="text-gray-700">{feature}</span>
                        </li>
                      ))}
                    </ul>
                    <Link href="/dashboard" className="mt-6 inline-flex items-center text-blue-600 font-medium">
                      Ask the AI assistant
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Link>
                  </div>
                  <div className="lg:w-1/2 bg-gray-100 p-4 relative min-h-[320px] flex items-center justify-center">
                    <div className="relative w-full h-full overflow-hidden rounded-lg shadow-inner">
                      <Image src="/ai-icon.svg" alt="AI Assistant" width={150} height={150} className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </section>

        {/* Dashboard Preview */}
        <section id="demo" className="py-24 relative">
          <div className="container mx-auto px-4">
            <div className="flex flex-col md:flex-row items-center gap-12">
              <div className="md:w-1/2 space-y-6">
                <h2 className="text-3xl md:text-4xl font-bold text-gray-900">Built for NBA Professionals</h2>
                <p className="text-lg text-gray-600">
                  Traditional NBA analysis requires multiple tools and platforms. Dime brings everything together in one powerful dashboard with AI-driven insights.
                </p>
                <ul className="space-y-3">
                  {[
                    'Comprehensive data from every NBA game',
                    'Customizable dashboard layouts',
                    'AI-powered insights and predictions',
                    'Shareable reports and visuals'
                  ].map((feature, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <div className="rounded-full bg-green-100 p-1">
                        <Check className="h-4 w-4 text-green-600" />
                      </div>
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>
                <div className="pt-4">
                  <Link href="/dashboard">
                    <Button className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white">
                      Try Demo Dashboard
                    </Button>
                  </Link>
                </div>
              </div>
              <div className="md:w-1/2 relative">
                <div className="relative rounded-lg border border-gray-200 overflow-hidden shadow-2xl mx-auto">
                  <div className="h-[42px] bg-gray-100 border-b border-gray-200 flex items-center px-4">
                    <div className="flex space-x-2">
                      <div className="w-3 h-3 rounded-full bg-red-400"></div>
                      <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                      <div className="w-3 h-3 rounded-full bg-green-400"></div>
                    </div>
                    <div className="ml-4 text-sm text-gray-500">Dime Dashboard</div>
                  </div>
                  <div className="bg-white p-0">
                    <Image 
                      src="/dashboard-mockup.svg" 
                      alt="NBA Dashboard Preview" 
                      width={600} 
                      height={400} 
                      className="w-full h-auto" 
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section id="pricing" className="py-24 bg-gray-50">
          <div className="container mx-auto px-4 text-center">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">Simple, Transparent Pricing</h2>
              <p className="text-lg text-gray-600">Start with our free trial or choose a plan that fits your needs.</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
              {/* Free Plan */}
              <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-gray-200 transition-transform hover:scale-105">
                <div className="p-8">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">Starter</h3>
                  <div className="text-4xl font-bold text-gray-900 mb-4">Free</div>
                  <p className="text-gray-600 mb-6">Perfect for casual fans to get started</p>
                  <ul className="space-y-3 text-left mb-8">
                    {['Live scores', 'Basic stats', 'Limited API access', '7-day data history'].map((feature, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-600" />
                        <span className="text-gray-700">{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href="/dashboard">
                    <Button variant="outline" className="w-full border-gray-300 hover:bg-gray-100">
                      Try Free
                    </Button>
                  </Link>
                </div>
              </div>
              
              {/* Pro Plan */}
              <div className="bg-white rounded-xl shadow-xl overflow-hidden border-2 border-blue-600 relative transition-transform hover:scale-105">
                <div className="absolute top-0 inset-x-0 bg-blue-600 text-white text-sm font-medium py-1">
                  Most Popular
                </div>
                <div className="p-8 pt-12">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">Professional</h3>
                  <div className="text-4xl font-bold text-gray-900 mb-4">$29<span className="text-lg text-gray-500">/mo</span></div>
                  <p className="text-gray-600 mb-6">For serious analysts and fantasy players</p>
                  <ul className="space-y-3 text-left mb-8">
                    {[
                      'Everything in Starter', 
                      'Advanced analytics', 
                      'Odds predictions', 
                      'Player comparison tools',
                      'Full history access'
                    ].map((feature, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-600" />
                        <span className="text-gray-700">{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href="/dashboard">
                    <Button className="w-full bg-blue-600 hover:bg-blue-700 text-white">
                      Start Free Trial
                    </Button>
                  </Link>
                </div>
              </div>
              
              {/* Enterprise Plan */}
              <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-gray-200 transition-transform hover:scale-105">
                <div className="p-8">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">Enterprise</h3>
                  <div className="text-4xl font-bold text-gray-900 mb-4">Custom</div>
                  <p className="text-gray-600 mb-6">For teams and professional organizations</p>
                  <ul className="space-y-3 text-left mb-8">
                    {[
                      'Everything in Professional', 
                      'AI research assistant', 
                      'Custom integrations', 
                      'API access',
                      'Dedicated support'
                    ].map((feature, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-600" />
                        <span className="text-gray-700">{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href="#">
                    <Button variant="outline" className="w-full border-gray-300 hover:bg-gray-100">
                      Contact Sales
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24">
          <div className="container mx-auto px-4">
            <div className="max-w-4xl mx-auto text-center p-12 rounded-xl bg-blue-600 shadow-lg">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">Ready to transform your NBA analysis?</h2>
              <p className="text-blue-100 mb-8 text-lg">Experience the future of basketball analytics today.</p>
              <div className="flex flex-col sm:flex-row justify-center gap-4">
                <Link href="/dashboard">
                  <Button size="lg" className="px-8 py-3 bg-white hover:bg-gray-100 text-blue-600 font-medium">
                    Launch Demo Dashboard
                  </Button>
                </Link>
                <Link href="#pricing">
                  <Button variant="outline" size="lg" className="px-8 py-3 border-white/70 text-white hover:bg-blue-700 font-medium">
                    View Pricing
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="py-16 border-t border-gray-200 bg-gray-50">
          <div className="container mx-auto px-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              <div>
                <div className="flex items-center mb-4">
                  <div className="rounded-lg bg-blue-600 p-2 mr-2">
                    <BarChart3 className="h-5 w-5 text-white" />
                  </div>
                  <span className="text-xl font-bold text-gray-900">Dime</span>
                </div>
                <p className="text-gray-600 mb-4">AI-powered NBA analytics platform for professionals and passionate fans.</p>
                <div className="flex space-x-4">
                  {['Twitter', 'LinkedIn', 'GitHub'].map(social => (
                    <Link key={social} href="#" className="text-gray-400 hover:text-blue-600">
                      {social}
                    </Link>
                  ))}
                </div>
              </div>
              
              <div>
                <h4 className="font-bold text-gray-900 mb-4">Product</h4>
                <ul className="space-y-2">
                  {['Features', 'Pricing', 'Case Studies', 'Documentation'].map(item => (
                    <li key={item}>
                      <Link href="#" className="text-gray-600 hover:text-blue-600">
                        {item}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
              
              <div>
                <h4 className="font-bold text-gray-900 mb-4">Company</h4>
                <ul className="space-y-2">
                  {['About', 'Blog', 'Careers', 'Press'].map(item => (
                    <li key={item}>
                      <Link href="#" className="text-gray-600 hover:text-blue-600">
                        {item}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
              
              <div>
                <h4 className="font-bold text-gray-900 mb-4">Legal</h4>
                <ul className="space-y-2">
                  {['Privacy', 'Terms', 'Security', 'Data Policy'].map(item => (
                    <li key={item}>
                      <Link href="#" className="text-gray-600 hover:text-blue-600">
                        {item}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            
            <div className="border-t border-gray-200 mt-12 pt-8 flex flex-col md:flex-row justify-between items-center">
              <div className="text-sm text-gray-600 mb-4 md:mb-0">
                2025 Dime Analytics. All rights reserved.
              </div>
              <div className="flex space-x-6">
                <Link href="#" className="text-sm text-gray-600 hover:text-blue-600">Privacy Policy</Link>
                <Link href="#" className="text-sm text-gray-600 hover:text-blue-600">Terms of Service</Link>
                <Link href="#" className="text-sm text-gray-600 hover:text-blue-600">Cookie Policy</Link>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

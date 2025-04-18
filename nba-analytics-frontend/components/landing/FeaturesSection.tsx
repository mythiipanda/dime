import { Card } from '@/components/ui/card';
import { PieChart, MapPin, Activity, Bell, ArrowRight } from 'lucide-react';
import Link from 'next/link';

export function FeaturesSection() {
  return (
    <section id="features" className="relative overflow-hidden bg-gradient-to-br from-blue-900 to-indigo-900 pt-40 pb-32 sm:pb-40 text-white">
      {/* Background gradient effects */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute -top-[40rem] left-[10%] -z-10 transform-gpu blur-3xl animate-[spin_20s_linear_infinite]" aria-hidden="true">
          <div className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#1D75FF] to-[#b134ff] opacity-20" 
               style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
        <div className="absolute top-[10%] right-[5%] -z-10 transform-gpu blur-3xl animate-[spin_20s_linear_infinite]" aria-hidden="true">
          <div className="aspect-[1155/678] w-[36.125rem] bg-gradient-to-r from-[#00DAFF] to-[#1D75FF] opacity-15" 
               style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
      </div>
      
      <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center mb-16">
        <div className="inline-flex items-center rounded-full px-5 py-2 mb-8 text-sm font-medium bg-blue-500/30 text-blue-200 ring-1 ring-inset ring-blue-400">
          <span>Agent for Sports Analysis</span>
          <span className="w-2 h-2 ml-2 rounded-full bg-blue-600"></span>
        </div>
        <h2 className="text-5xl font-bold tracking-tight text-white sm:text-6xl mb-8">Sports Analysis <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">Reimagined</span> by Dime</h2>
        <p className="text-xl leading-8 text-gray-200 max-w-2xl mx-auto mb-14">Professional-grade NBA analytics, trend detection, lineup optimization, and predictive insights for informed management decisions.</p>
        <Link href="/dashboard" className="inline-flex items-center px-8 py-4 mb-24 text-md font-semibold text-white bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg shadow-lg hover:from-blue-600 hover:to-cyan-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 gap-2 transition-all duration-300">
          Get Started with Dime <ArrowRight className="h-4 w-4 ml-1" />
        </Link>
      </div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 relative z-10">
        {/* Real-Time Win Probability */}
        <Card className="p-8 bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-600 shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-xl hover:scale-105 hover:bg-gray-800 flex flex-col items-start text-left">
          <div className="p-3 bg-blue-500/20 rounded-lg mb-5">
            <PieChart className="h-7 w-7 text-blue-400" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-3">Real-Time Win Probability</h3>
          <p className="text-sm text-gray-300 leading-relaxed">Live win projections recalculated after every possession with advanced modeling.</p>
        </Card>
        {/* Interactive Shot Maps */}
        <Card className="p-8 bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-600 shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-xl hover:scale-105 hover:bg-gray-800 flex flex-col items-start text-left">
          <div className="p-3 bg-green-500/20 rounded-lg mb-5">
            <MapPin className="h-7 w-7 text-green-400" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-3">Interactive Shot Maps</h3>
          <p className="text-sm text-gray-300 leading-relaxed">Visualize shot distributions and hotspots with dynamic, filterable heatmaps.</p>
        </Card>
        {/* Lineup Optimization */}
        <Card className="p-8 bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-600 shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-xl hover:scale-105 hover:bg-gray-800 flex flex-col items-start text-left">
          <div className="p-3 bg-purple-500/20 rounded-lg mb-5">
            <Activity className="h-7 w-7 text-purple-400" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-3">Lineup Optimization</h3>
          <p className="text-sm text-gray-300 leading-relaxed">Simulate rotations and identify optimal lineups to maximize performance.</p>
        </Card>
        {/* Real-Time Insights & Alerts */}
        <Card className="p-8 bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-600 shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-xl hover:scale-105 hover:bg-gray-800 flex flex-col items-start text-left">
          <div className="p-3 bg-orange-500/20 rounded-lg mb-5">
            <Bell className="h-7 w-7 text-orange-400" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-3">Real-Time Insights & Alerts</h3>
          <p className="text-sm text-gray-300 leading-relaxed">Receive instant predictive insights and automated alerts to stay ahead of game-changing moments.</p>
        </Card>
      </div>
    </section>
  );
} 
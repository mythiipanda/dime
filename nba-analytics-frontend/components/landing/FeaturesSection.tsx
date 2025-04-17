import { Card } from '@/components/ui/card';
import { PieChart, MapPin, Activity, Bell, ArrowRight } from 'lucide-react';
import Link from 'next/link';

export function FeaturesSection() {
  return (
    <section id="features" className="relative overflow-hidden bg-gradient-to-b from-white to-slate-50 pt-32 pb-24 sm:pb-32">
      {/* Background gradient effects */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute -top-[40rem] left-[10%] -z-10 transform-gpu blur-3xl" aria-hidden="true">
          <div className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#1D75FF] to-[#b134ff] opacity-20" 
               style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
        <div className="absolute top-[10%] right-[5%] -z-10 transform-gpu blur-3xl" aria-hidden="true">
          <div className="aspect-[1155/678] w-[36.125rem] bg-gradient-to-r from-[#00DAFF] to-[#1D75FF] opacity-15" 
               style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
      </div>
      
      <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center mb-16">
        <div className="inline-flex items-center rounded-full px-3 py-1 mb-6 text-sm font-medium bg-blue-50 text-blue-600 ring-1 ring-inset ring-blue-500/20">
          <span>Agent for Sports Analysis</span>
          <span className="w-2 h-2 ml-2 rounded-full bg-blue-600"></span>
        </div>
        <h2 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl mb-6">Sports Analysis <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Reimagined</span> by Dime</h2>
        <p className="text-xl leading-8 text-gray-600 max-w-2xl mx-auto mb-12">Data-centric decisions powered by professional analysis, machine learning models, and predictive insights.</p>
        <Link href="/dashboard" className="inline-flex items-center px-5 py-2.5 mb-16 text-md font-medium text-white bg-blue-600 rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 gap-1">
          Get Started with Dime <ArrowRight className="h-4 w-4 ml-1" />
        </Link>
      </div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 relative z-10">
        {/* Real-Time Win Probability */}
        <Card className="p-6 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-all duration-300 hover:translate-y-[-4px] flex flex-col items-start text-left">
          <div className="p-2 bg-blue-100 rounded-lg mb-4">
            <PieChart className="h-6 w-6 text-blue-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Real-Time Win Probability</h3>
          <p className="text-sm text-gray-600 leading-relaxed">Live win projections recalculated after every possession with advanced modeling.</p>
        </Card>
        {/* Interactive Shot Maps */}
        <Card className="p-6 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-all duration-300 hover:translate-y-[-4px] flex flex-col items-start text-left">
          <div className="p-2 bg-green-100 rounded-lg mb-4">
            <MapPin className="h-6 w-6 text-green-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Interactive Shot Maps</h3>
          <p className="text-sm text-gray-600 leading-relaxed">Visualize shot distributions and hotspots with dynamic, filterable heatmaps.</p>
        </Card>
        {/* Lineup Optimization */}
        <Card className="p-6 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-all duration-300 hover:translate-y-[-4px] flex flex-col items-start text-left">
          <div className="p-2 bg-purple-100 rounded-lg mb-4">
            <Activity className="h-6 w-6 text-purple-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Lineup Optimization</h3>
          <p className="text-sm text-gray-600 leading-relaxed">Simulate rotations and identify optimal lineups to maximize performance.</p>
        </Card>
        {/* Real-Time Insights & Alerts */}
        <Card className="p-6 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-all duration-300 hover:translate-y-[-4px] flex flex-col items-start text-left">
          <div className="p-2 bg-orange-100 rounded-lg mb-4">
            <Bell className="h-6 w-6 text-orange-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Real-Time Insights & Alerts</h3>
          <p className="text-sm text-gray-600 leading-relaxed">Receive instant predictive insights and automated alerts to stay ahead of game-changing moments.</p>
        </Card>
      </div>
    </section>
  );
} 
import { Card } from '@/components/ui/card';
import { PieChart, MapPin, Activity, Bell, ArrowRight, BarChartHorizontal } from 'lucide-react';
import Link from 'next/link';

export function FeaturesSection() {
  const features = [
    {
      icon: <PieChart className="h-6 w-6 text-[#99FFCC]" />,
      title: "Live Win Probability",
      description: "Track real-time win projections, recalculated possession by possession using advanced modeling.",
    },
    {
      icon: <MapPin className="h-6 w-6 text-[#99FFCC]" />,
      title: "Interactive Shot Charts",
      description: "Visualize player and team shooting performance with dynamic, filterable shot charts.",
    },
    {
      icon: <Activity className="h-6 w-6 text-[#99FFCC]" />,
      title: "Advanced Stat Analysis",
      description: "Dive deep into hustle stats, tracking data, advanced box scores, and lineup efficiency.",
    },
    {
      icon: <BarChartHorizontal className="h-6 w-6 text-[#99FFCC]" />,
      title: "Player & Team Comparison",
      description: "Compare players or teams head-to-head across a wide range of statistical categories.",
    },
  ];

  return (
    <section id="features" className="relative overflow-hidden pt-24 pb-24 text-white">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="text-center mb-16">
          <div className="inline-flex items-center rounded-full px-4 py-1 mb-6 text-xs font-medium bg-[#1A1C1F] border border-[#2A2C31] text-[#99FFCC]">
            <span>Core Capabilities</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">
            Uncover Insights with <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#99FFCC] to-[#33FF99]">Powerful Tools</span>
          </h2>
          <p className="text-lg leading-7 text-[#A7BEBE] max-w-2xl mx-auto mb-10">From live game data to deep statistical comparisons, Dime provides the tools you need for comprehensive NBA analysis.</p>
          <Link href="/dashboard" className="inline-flex items-center px-8 py-3 text-base font-semibold text-[#000E0F] bg-[#99FFCC] rounded-full shadow-lg hover:bg-opacity-90 focus:outline-none transition-all duration-300 group">
            Explore Features <ArrowRight className="h-5 w-5 ml-2 text-[#000E0F]/80 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 relative z-10">
          {features.map((feature, index) => (
            <div key={index} className="group relative">
              <div className="absolute -inset-px bg-gradient-to-br from-[#99FFCC]/30 to-[#33FF99]/30 rounded-xl blur-lg opacity-0 group-hover:opacity-70 transition duration-300"></div>
              <Card className="relative h-full bg-[#0F1A1B]/70 backdrop-blur-sm rounded-xl border border-white/10 p-6 shadow-lg hover:border-white/20 transition-all duration-300 flex flex-col">
                <div className="p-3 bg-[#1A1C1F]/50 border border-white/10 rounded-lg mb-5 inline-flex items-center justify-center w-12 h-12">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-[#A7BEBE] leading-relaxed flex-grow">{feature.description}</p>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
} 
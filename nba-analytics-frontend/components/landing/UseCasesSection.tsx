import React from 'react';
import { Card } from '@/components/ui/card';
import { TrendingUp, BarChart2, Activity, UserCheck, Trophy, DollarSign, Users, Calendar, Star, BookOpen, RadioTower } from 'lucide-react';

export function UseCasesSection() {
  const useCases = [
    { icon: <RadioTower className="h-6 w-6 text-[#99FFCC]" />, title: 'Live Game Tracking', description: 'Follow games in real-time with live scores, play-by-play, and win probability updates.' },
    { icon: <BarChart2 className="h-6 w-6 text-[#99FFCC]" />, title: 'Advanced Player Analysis', description: 'Go beyond box scores with shot charts, advanced splits, and career performance trends.' },
    { icon: <UserCheck className="h-6 w-6 text-[#99FFCC]" />, title: 'Player Comparison Engine', description: 'Compare players head-to-head across seasons, game types, or specific situations.' },
    { icon: <TrendingUp className="h-6 w-6 text-[#99FFCC]" />, title: 'Team Performance Insights', description: 'Analyze team stats, trends, roster composition, and passing dynamics.' },
    { icon: <Trophy className="h-6 w-6 text-[#99FFCC]" />, title: 'League Leaders & Standings', description: 'Track top performers and monitor playoff races with up-to-date league data.' },
    { icon: <Star className="h-6 w-6 text-[#99FFCC]" />, title: 'AI-Powered Scouting', description: 'Leverage AI to analyze draft prospects, identify player archetypes, and generate reports.' },
    { icon: <Activity className="h-6 w-6 text-[#99FFCC]" />, title: 'Hustle & Tracking Stats', description: 'Measure player impact beyond traditional stats with hustle and detailed tracking data.' },
    { icon: <BookOpen className="h-6 w-6 text-[#99FFCC]" />, title: 'AI Research Assistant', description: 'Ask natural language questions to get instant answers, charts, and data tables.' }
  ];

  return (
    <section id="usecases" className="py-32 relative overflow-hidden text-white bg-[#000E0F]">
      <div className="container mx-auto max-w-7xl px-4">
        <h2 className="text-4xl md:text-5xl font-bold text-white text-center mb-16">
          Transform Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#99FFCC] to-[#33FF99]">Analysis Workflow</span>
        </h2>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
          {useCases.map((uc) => (
            <div key={uc.title} className="group relative">
              <div className="absolute -inset-px bg-gradient-to-br from-[#99FFCC]/20 to-[#33FF99]/20 rounded-xl blur-lg opacity-0 group-hover:opacity-70 transition duration-300"></div>
              <Card className="relative h-full bg-[#0F1A1B]/70 backdrop-blur-sm rounded-xl border border-white/10 p-6 shadow-lg hover:border-white/20 transition-all duration-300 flex flex-col">
                <div className="p-3 bg-[#1A1C1F]/50 border border-white/10 rounded-lg mb-5 inline-flex items-center justify-center w-12 h-12">
                  {uc.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{uc.title}</h3>
                <p className="text-[#A7BEBE] leading-relaxed flex-grow">{uc.description}</p>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

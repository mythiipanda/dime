import React from 'react';
import { Card } from '@/components/ui/card';
import { TrendingUp, BarChart2, Activity, UserCheck, Trophy, DollarSign, Users, Calendar, Star, BookOpen } from 'lucide-react';

export function UseCasesSection() {
  const useCases = [
    { icon: <TrendingUp className="h-6 w-6 text-blue-600" />, title: 'Player Performance Trends', description: 'Analyze player performance fluctuations over seasons to uncover development patterns and peak metrics.' },
    { icon: <BarChart2 className="h-6 w-6 text-green-600" />, title: 'Team Standings & Projections', description: 'Visualize current standings and forecast playoff probabilities with dynamic, data-driven models.' },
    { icon: <Activity className="h-6 w-6 text-red-600" />, title: 'Injury Impact Analysis', description: 'Assess the impact of injuries on team performance and simulate lineup adjustments in real time.' },
    { icon: <UserCheck className="h-6 w-6 text-purple-600" />, title: 'Lineup Optimization', description: 'Optimize on-court rotations and lineups to maximize efficiency and player synergy.' },
    { icon: <Trophy className="h-6 w-6 text-yellow-600" />, title: 'Draft & Scouting Insights', description: 'Evaluate draft prospects and generate insightful scouting reports with advanced analytics.' },
    { icon: <DollarSign className="h-6 w-6 text-indigo-600" />, title: 'Contract & Salary Analysis', description: 'Analyze contract structures, cap implications, and negotiate optimal deals leveraging financial models.' },
    { icon: <Users className="h-6 w-6 text-teal-600" />, title: 'Sponsorship ROI Metrics', description: 'Quantify sponsorship performance and maximize revenue opportunities with data-backed insights.' },
    { icon: <Calendar className="h-6 w-6 text-pink-600" />, title: 'Game Scheduling & Ticket Pricing', description: 'Forecast demand and optimize schedule and pricing strategies to boost attendance and revenue.' },
    { icon: <Star className="h-6 w-6 text-amber-600" />, title: 'Fantasy Team Analytics', description: 'Leverage predictive models to assemble and manage winning fantasy lineups for every matchup.' },
    { icon: <BookOpen className="h-6 w-6 text-gray-600" />, title: 'Betting Odds Predictions', description: 'Predict game outcomes and betting lines with high accuracy using real-time statistical analysis.' }
  ];

  return (
    <section id="usecases" className="py-32 sm:py-40 bg-gradient-to-br from-gray-900 to-gray-800 text-white">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <h2 className="text-5xl font-bold text-white text-center mb-16">Use Case Gallery</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-10">
          {useCases.map((uc) => (
            <Card key={uc.title} className="p-8 bg-gray-800/80 backdrop-blur-sm border border-gray-600 rounded-xl shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-2xl hover:scale-105 hover:bg-gray-800 flex flex-col items-start text-left">
              <div className="p-4 bg-blue-500/20 rounded-full mb-5 inline-block">{uc.icon}</div>
              <h3 className="text-xl font-semibold text-white mb-3">{uc.title}</h3>
              <p className="text-sm text-gray-300 leading-relaxed">{uc.description}</p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

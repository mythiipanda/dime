import React from 'react';
import { Card } from '@/components/ui/card';
import { TrendingUp, BarChart2, Activity, UserCheck, Trophy, DollarSign, Users, Calendar, Star, BookOpen, RadioTower } from 'lucide-react';

export function UseCasesSection() {
  const useCases = [
    { icon: <RadioTower className="h-6 w-6 text-primary" />, title: 'Live Game Tracking', description: 'Follow games in real-time with live scores, play-by-play, and win probability updates.' },
    { icon: <BarChart2 className="h-6 w-6 text-primary" />, title: 'Advanced Player Analysis', description: 'Go beyond box scores with shot charts, advanced splits, and career performance trends.' },
    { icon: <UserCheck className="h-6 w-6 text-primary" />, title: 'Player Comparison Engine', description: 'Compare players head-to-head across seasons, game types, or specific situations.' },
    { icon: <TrendingUp className="h-6 w-6 text-primary" />, title: 'Team Performance Insights', description: 'Analyze team stats, trends, roster composition, and passing dynamics.' },
    { icon: <Trophy className="h-6 w-6 text-primary" />, title: 'League Leaders & Standings', description: 'Track top performers and monitor playoff races with up-to-date league data.' },
    { icon: <Star className="h-6 w-6 text-primary" />, title: 'AI-Powered Scouting', description: 'Leverage AI to analyze draft prospects, identify player archetypes, and generate reports.' },
    { icon: <Activity className="h-6 w-6 text-primary" />, title: 'Hustle & Tracking Stats', description: 'Measure player impact beyond traditional stats with hustle and detailed tracking data.' },
    { icon: <BookOpen className="h-6 w-6 text-primary" />, title: 'AI Research Assistant', description: 'Ask natural language questions to get instant answers, charts, and data tables.' }
  ];

  return (
    <section id="usecases" className="py-32 relative overflow-hidden bg-background text-foreground">
      <div className="container mx-auto max-w-7xl px-4">
        <h2 className="text-4xl md:text-5xl font-bold text-foreground text-center mb-16">
          Transform Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">Analysis Workflow</span>
        </h2>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
          {useCases.map((uc) => (
            <div key={uc.title} className="group relative">
              <div className="absolute -inset-px bg-gradient-to-br from-primary/20 to-secondary/20 rounded-xl blur-lg opacity-0 group-hover:opacity-70 transition duration-300"></div>
              <Card className="relative h-full p-6 flex flex-col transition-all duration-300 shadow-lg hover:shadow-xl">
                <div className="p-3 bg-muted/20 rounded-lg mb-5 inline-flex items-center justify-center w-12 h-12">
                  {uc.icon}
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-3">{uc.title}</h3>
                <p className="text-muted-foreground leading-relaxed flex-grow">{uc.description}</p>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

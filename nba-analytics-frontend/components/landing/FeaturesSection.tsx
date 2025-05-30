import { Card } from '@/components/ui/card';
import { PieChart, MapPin, Activity, ArrowRight, BarChartHorizontal } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils'; // Import cn

export function FeaturesSection() {
  const features = [
    {
      icon: <PieChart className="h-6 w-6 text-primary" />,
      title: "Live Win Probability",
      description: "Track real-time win projections, recalculated possession by possession using advanced modeling.",
    },
    {
      icon: <MapPin className="h-6 w-6 text-primary" />,
      title: "Interactive Shot Charts",
      description: "Visualize player and team shooting performance with dynamic, filterable shot charts.",
    },
    {
      icon: <Activity className="h-6 w-6 text-primary" />,
      title: "Advanced Stat Analysis",
      description: "Dive deep into hustle stats, tracking data, advanced box scores, and lineup efficiency.",
    },
    {
      icon: <BarChartHorizontal className="h-6 w-6 text-primary" />,
      title: "Player & Team Comparison",
      description: "Compare players or teams head-to-head across a wide range of statistical categories.",
    },
  ];

  return (
    <section id="features" className="relative overflow-hidden py-24 bg-background text-foreground">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="text-center mb-16">
          <div className="inline-flex items-center rounded-full px-4 py-1 mb-6 text-xs font-medium bg-muted/20 border border-border text-muted-foreground">
            <span>Core Capabilities</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground mb-6">
            Uncover Insights with <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">Powerful Tools</span>
          </h2>
          <p className="text-lg leading-7 text-muted-foreground max-w-2xl mx-auto mb-10">From live game data to deep statistical comparisons, Dime provides the tools you need for comprehensive NBA analysis.</p>
          <Link href="/overview" className="group">
            <Button>
              Explore Features <ArrowRight className="h-5 w-5 ml-2 transition-transform group-hover:translate-x-1" />
            </Button>
          </Link>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 relative z-10">
          {features.map((feature, index) => (
            <div key={index} className="group relative">
              <div className="absolute -inset-px bg-gradient-to-br from-primary/30 to-secondary/30 rounded-xl blur-lg opacity-0 group-hover:opacity-70 transition-opacity duration-300"></div> {/* Changed transition to transition-opacity */}
              <Card className={cn(
                "relative h-full p-6 flex flex-col transition-all duration-300 shadow-lg hover:shadow-xl group-hover:scale-105",
                "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
              )} style={{ animationDelay: `${index * 100}ms` }}>
                <div className="p-3 bg-muted/20 rounded-lg mb-5 inline-flex items-center justify-center w-12 h-12">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-3">{feature.title}</h3>
                <p className="text-muted-foreground leading-relaxed flex-grow">{feature.description}</p>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
} 
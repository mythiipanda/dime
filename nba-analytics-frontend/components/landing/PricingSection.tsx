import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

export function PricingSection() {
  const plans = [
    {
      name: "Analyst",
      price: "$15",
      freq: "/month",
      description: "For individuals automating basic NBA data analysis.",
      features: [
        "Core stats access & visualization",
        "Delegate basic player/team lookups",
        "Standard AI analysis models",
        "Community forum support",
      ],
      buttonText: "Start Analyzing",
      buttonVariant: "outline",
      featured: false,
      animationDelay: "100ms",
    },
    {
      name: "Pro Analyst",
      price: "$35",
      freq: "/month",
      description: "For power users automating advanced analysis & scouting.",
      features: [
        "All Analyst features",
        "Delegate advanced scouting tasks",
        "Interactive shot chart generation & analysis",
        "AI game predictions & basic simulations",
        "Player comparison engine",
        "Priority email support",
      ],
      buttonText: "Activate Pro Agent",
      buttonVariant: "default",
      featured: true,
      animationDelay: "200ms",
    },
    {
      name: "Team / Enterprise",
      price: "Custom",
      freq: "",
      description: "For teams, media ops, and organizations needing scaled AI.",
      features: [
        "All Pro Analyst features",
        "High-volume autonomous agent tasks",
        "Advanced trade & draft simulations",
        "Custom AI model integration/tuning",
        "API access & dedicated support",
      ],
      buttonText: "Contact Sales",
      buttonVariant: "outline",
      featured: false,
      animationDelay: "300ms",
    },
  ];

  return (
    <section id="pricing" className="py-16 md:py-24 bg-gradient-to-b from-blue-950/80 to-gray-950">
      <div className="container mx-auto max-w-7xl px-4 text-center mb-12 md:mb-16 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-3">
          Flexible Plans for Every Analyst
        </h2>
        <p className="text-lg leading-8 text-gray-300 max-w-2xl mx-auto">
          Scale your analytical power. Choose the Dime AI agent configuration that fits your needs, from individual insights to enterprise-level operations.
        </p>
      </div>
      
      <div className="container mx-auto max-w-5xl px-4 grid grid-cols-1 md:grid-cols-3 gap-8 items-stretch">
        {plans.map((plan) => (
          <Card key={plan.name} className={cn(
            `relative flex flex-col p-6 rounded-xl shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1`,
            plan.featured 
              ? 'bg-gradient-to-br from-gray-800 via-gray-900 to-blue-900/70 border-2 border-cyan-400/70'
              : 'bg-gray-800/60 backdrop-blur-md border border-white/10',
            "animate-in fade-in-0 slide-in-from-bottom-5 duration-500"
          )} style={{ animationDelay: plan.animationDelay }}>
            {plan.featured && (
              <div className="absolute top-0 -translate-y-1/2 left-1/2 -translate-x-1/2">
                <span className="bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-xs font-semibold px-4 py-1 rounded-full shadow-md">
                  Most Popular
                </span>
              </div>
            )}
            
            <CardHeader className="pt-2 pb-6 text-center">
              <CardTitle className="text-xl font-semibold text-gray-100 mb-1">{plan.name}</CardTitle>
              <div className="flex items-baseline justify-center text-white">
                <span className="text-4xl font-extrabold tracking-tight">{plan.price}</span>
                {plan.freq && <span className="ml-1 text-xl font-medium text-gray-400">{plan.freq}</span>}
              </div>
              <CardDescription className="mt-2 text-sm text-gray-400 min-h-[40px]">{plan.description}</CardDescription>
            </CardHeader>
            
            <div className="flex-grow mb-8 border-t border-white/10 pt-6">
              <ul className="space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start">
                    <Check className="flex-shrink-0 h-5 w-5 text-cyan-400 mt-0.5" />
                    <span className="ml-3 text-gray-300 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            <div className="mt-auto">
               <Button 
                 className={cn(
                    "w-full font-semibold py-3 text-base shadow hover:shadow-md transition-all",
                    plan.featured 
                      ? 'bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white' 
                      : 'bg-gray-700/60 hover:bg-gray-600/80 text-gray-200 border border-white/20'
                 )}
                 variant={plan.featured ? 'default' : 'outline'}
                >
                 {plan.buttonText}
               </Button>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
} 
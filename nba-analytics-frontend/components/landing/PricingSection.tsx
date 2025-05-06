import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils'; // Import cn

export function PricingSection() {
  const plans = [
    {
      name: "Hobbyist",
      price: "$9",
      freq: "/mo",
      features: [
        "Basic Stats Access",
        "Limited AI Queries",
        "Community Support",
      ],
      buttonText: "Get Started",
      buttonVariant: "secondary", // Use a secondary style for non-featured
      featured: false,
    },
    {
      name: "Pro",
      price: "$29",
      freq: "/mo",
      features: [
        "Full Stats Access",
        "Advanced AI Queries",
        "Player Comparisons",
        "Trend Detection",
        "Priority Support",
      ],
      buttonText: "Choose Pro",
      buttonVariant: "primary", // Primary style for featured
      featured: true,
    },
    {
      name: "Enterprise",
      price: "Custom",
      freq: "",
      features: [
        "API Access",
        "Custom Models",
        "Dedicated Support",
      ],
      buttonText: "Contact Us",
      buttonVariant: "secondary", // Secondary style
      featured: false,
    },
  ];

  return (
    <section id="pricing" className="py-32 relative overflow-hidden bg-background text-foreground">
      {/* Section Title - Updated styling */}
      <div className="container mx-auto max-w-7xl px-4 text-center mb-16 relative z-10">
        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground mb-4">
          Flexible <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">Pricing</span>
        </h2>
        <p className="text-lg leading-8 text-muted-foreground max-w-2xl mx-auto">Choose the plan that scales with your analysis needs.</p>
      </div>
      
      {/* Pricing Cards Container - Updated Card styling */}
      <div className="container mx-auto max-w-4xl px-4 grid grid-cols-1 md:grid-cols-3 gap-8 items-start relative z-10">
        {plans.map((plan, index) => ( // Added index for animation delay
          <div key={plan.name} className={`relative group ${plan.featured ? 'md:-mt-4 md:mb-4' : ''}`}>
            {/* Glow effect */}
            <div className={`absolute -inset-px rounded-2xl blur-lg opacity-0 group-hover:opacity-70 transition-opacity duration-300 ${plan.featured ? 'bg-gradient-to-br from-primary/40 to-secondary/40' : 'bg-gradient-to-br from-primary/20 to-secondary/20'}`}></div> {/* Changed transition to transition-opacity */}
            <Card className={cn(
              `relative h-full p-8 flex flex-col transition-all duration-300 shadow-md hover:shadow-lg group-hover:scale-105`,
              plan.featured ? 'border border-primary/50' : '',
              "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
            )} style={{ animationDelay: `${index * 100}ms` }}>
              {plan.featured && (
                <div className="absolute top-0 inset-x-0 flex justify-center -translate-y-1/2">
                  <div className="bg-gradient-to-r from-primary to-secondary text-foreground text-xs font-bold px-5 py-1 rounded-full shadow-lg">
                    Most Popular
                  </div>
                </div>
              )}
              
              <div className={`mb-6 ${plan.featured ? 'pt-4' : ''}`}>
                <h3 className="text-xl font-medium text-foreground mb-2">{plan.name}</h3>
                <div className="flex items-baseline text-foreground">
                  <span className="text-5xl font-bold tracking-tight">{plan.price}</span>
                  {plan.freq && <span className="ml-1 text-xl font-semibold text-muted-foreground">{plan.freq}</span>}
                </div>
              </div>
              
              <div className="mt-2 mb-8 border-t border-muted-foreground/10 pt-6 flex-grow">
                <ul className="space-y-4">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex">
                      <Check className="flex-shrink-0 h-5 w-5 text-primary" />
                      <span className="ml-3 text-muted-foreground text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
              
              <div className="mt-auto">
                 {plan.buttonVariant === 'primary' ? (
                   <Button className="w-full">{plan.buttonText}</Button>
                 ) : (
                   <Button variant="outline" className="w-full">{plan.buttonText}</Button>
                 )}
              </div>
            </Card>
          </div>
        ))}
      </div>
    </section>
  );
} 
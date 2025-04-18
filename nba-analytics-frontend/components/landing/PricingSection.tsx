import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Check } from 'lucide-react';

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
    <section id="pricing" className="py-32 relative overflow-hidden">
      {/* Section Title - Updated styling */}
      <div className="container mx-auto max-w-7xl px-4 text-center mb-16 relative z-10">
        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-4">
          Flexible <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#99FFCC] to-[#33FF99]">Pricing</span>
        </h2>
        <p className="text-lg leading-8 text-[#A7BEBE] max-w-2xl mx-auto">Choose the plan that scales with your analysis needs.</p>
      </div>
      
      {/* Pricing Cards Container - Updated Card styling */}
      <div className="container mx-auto max-w-4xl px-4 grid grid-cols-1 md:grid-cols-3 gap-8 items-start relative z-10">
        {plans.map((plan) => (
          <div key={plan.name} className={`relative group ${plan.featured ? 'md:-mt-4 md:mb-4' : ''}`}>
            {/* Glow effect */}
            <div className={`absolute -inset-px rounded-2xl blur-lg opacity-0 group-hover:opacity-70 transition duration-300 ${plan.featured ? 'bg-gradient-to-br from-[#99FFCC]/40 to-[#33FF99]/40' : 'bg-gradient-to-br from-[#99FFCC]/20 to-[#33FF99]/20'}`}></div>
            <Card 
              className={`relative h-full p-8 bg-[#0F1A1B]/70 backdrop-blur-sm rounded-2xl border ${plan.featured ? 'border-[#99FFCC]/50' : 'border-white/10'} shadow-xl hover:border-white/20 flex flex-col transition-all duration-300`}
            >
              {plan.featured && (
                <div className="absolute top-0 inset-x-0 flex justify-center -translate-y-1/2">
                  <div className="bg-gradient-to-r from-[#99FFCC] to-[#33FF99] text-[#000E0F] text-xs font-bold px-5 py-1 rounded-full shadow-lg">
                    Most Popular
                  </div>
                </div>
              )}
              
              <div className={`mb-6 ${plan.featured ? 'pt-4' : ''}`}>
                <h3 className="text-xl font-medium text-white mb-2">{plan.name}</h3>
                <div className="flex items-baseline text-white">
                  <span className="text-5xl font-bold tracking-tight">{plan.price}</span>
                  {plan.freq && <span className="ml-1 text-xl font-semibold text-[#A7BEBE]">{plan.freq}</span>}
                </div>
              </div>
              
              <div className="mt-2 mb-8 border-t border-white/10 pt-6 flex-grow">
                <ul className="space-y-4">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex">
                      <Check className="flex-shrink-0 h-5 w-5 text-[#99FFCC]" />
                      <span className="ml-3 text-[#A7BEBE] text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
              
              <div className="mt-auto">
                 {plan.buttonVariant === 'primary' ? (
                   <Button className="w-full bg-[#99FFCC] text-[#000E0F] hover:bg-opacity-90 font-semibold py-3 rounded-full shadow-lg transition-all duration-300">
                     {plan.buttonText}
                   </Button>
                 ) : (
                   <Button variant="outline" className="w-full text-[#A7BEBE] border-white/20 hover:bg-white/5 hover:border-white/30 hover:text-white font-medium py-3 rounded-full shadow-md transition-all duration-300">
                     {plan.buttonText}
                   </Button>
                 )}
              </div>
            </Card>
          </div>
        ))}
      </div>
    </section>
  );
} 
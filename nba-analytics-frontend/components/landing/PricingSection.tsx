import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export function PricingSection() {
  return (
    <section id="pricing" className="bg-gradient-to-b from-white to-slate-50 py-24 sm:py-32 relative overflow-hidden">
      {/* Background gradient effects */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute bottom-0 left-[20%] -z-10 transform-gpu blur-3xl" aria-hidden="true">
          <div className="aspect-[1155/678] w-[50rem] bg-gradient-to-tr from-[#1D75FF] to-[#b134ff] opacity-20" 
               style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
      </div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center mb-16 relative z-10">
        <div className="inline-flex items-center rounded-full px-3 py-1 mb-6 text-sm font-medium bg-blue-50 text-blue-600 ring-1 ring-inset ring-blue-500/20">
          <span>Simple Pricing</span>
          <span className="w-2 h-2 ml-2 rounded-full bg-blue-600"></span>
        </div>
        <h2 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl mb-4">Flexible <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Pricing</span></h2>
        <p className="text-lg leading-8 text-gray-600">Choose the plan that scales with your analysis needs.</p>
      </div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 md:grid-cols-3 gap-8 relative z-10">
        {/* Pricing Card 1 */}
        <Card className="p-8 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-all duration-300 hover:translate-y-[-4px] flex flex-col text-center">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Hobbyist</h3>
          <p className="text-4xl font-bold text-gray-900 mb-4">$9<span className="text-base font-medium text-gray-500">/mo</span></p>
          <ul className="text-sm text-gray-600 space-y-2 mb-6 text-left list-disc list-inside">
            <li>Basic Stats Access</li>
            <li>Limited AI Queries</li>
            <li>Community Support</li>
          </ul>
          <Button variant="outline" className="mt-auto hover:bg-gray-50 transition-colors duration-300">Get Started</Button>
        </Card>
        {/* Pricing Card 2 (Featured) */}
        <Card className="p-8 rounded-xl border-2 border-blue-600 shadow-xl relative flex flex-col text-center scale-105 bg-gradient-to-b from-white to-blue-50/30 transition-all duration-300 hover:shadow-2xl hover:translate-y-[-4px]">
          <div className="absolute top-0 right-0 -mt-3 mr-3 bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-md">Most Popular</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Pro</h3>
          <p className="text-4xl font-bold text-gray-900 mb-4">$29<span className="text-base font-medium text-gray-500">/mo</span></p>
          <ul className="text-sm text-gray-600 space-y-2 mb-6 text-left list-disc list-inside">
            <li>Full Stats Access</li>
            <li>Advanced AI Queries</li>
            <li>Player Comparisons</li>
            <li>Trend Detection</li>
            <li>Priority Support</li>
          </ul>
          <Button className="mt-auto bg-blue-600 text-white hover:bg-blue-700 shadow-md hover:shadow-lg transition-shadow duration-300">Choose Pro</Button>
        </Card>
        {/* Pricing Card 3 */}
        <Card className="p-8 rounded-xl border border-gray-200 shadow-sm hover:shadow-lg transition-all duration-300 hover:translate-y-[-4px] flex flex-col text-center">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Enterprise</h3>
          <p className="text-4xl font-bold text-gray-900 mb-4">Custom</p>
          <ul className="text-sm text-gray-600 space-y-2 mb-6 text-left list-disc list-inside">
            <li>API Access</li>
            <li>Custom Models</li>
            <li>Dedicated Support</li>
          </ul>
          <Button variant="outline" className="mt-auto">Contact Us</Button>
        </Card>
      </div>
    </section>
  );
} 
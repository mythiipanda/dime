import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export function PricingSection() {
  return (
    <section id="pricing" className="bg-gradient-to-br from-gray-800 to-gray-900 py-32 sm:py-40 relative overflow-hidden text-white">
      {/* Background gradient effects */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute bottom-0 left-[20%] -z-10 transform-gpu blur-3xl" aria-hidden="true">
          <div className="aspect-[1155/678] w-[50rem] bg-gradient-to-tr from-[#1D75FF] to-[#b134ff] opacity-30" 
               style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
      </div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center mb-16 relative z-10">
        <div className="inline-flex items-center rounded-full px-5 py-2 mb-8 text-sm font-medium bg-blue-500/30 text-blue-200 ring-1 ring-inset ring-blue-400">
          <span>Simple Pricing</span>
          <span className="w-2 h-2 ml-2 rounded-full bg-blue-600"></span>
        </div>
        <h2 className="text-5xl font-bold tracking-tight text-white sm:text-6xl mb-6">Flexible <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">Pricing</span></h2>
        <p className="text-xl leading-8 text-gray-200 mb-16">Choose the plan that scales with your analysis needs.</p>
      </div>
      <div className="mx-auto max-w-7xl px-6 lg:px-8 grid grid-cols-1 md:grid-cols-3 gap-10 relative z-10">
        {/* Pricing Card 1 */}
        <Card className="p-10 bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-600 shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-xl hover:scale-105 hover:bg-gray-800 flex flex-col text-center">
          <h3 className="text-xl font-semibold text-white mb-3">Hobbyist</h3>
          <p className="text-4xl font-bold text-white mb-6">$9<span className="text-base font-medium text-gray-400">/mo</span></p>
          <ul className="text-sm text-gray-300 space-y-3 mb-8 text-left list-disc list-inside">
            <li>Basic Stats Access</li>
            <li>Limited AI Queries</li>
            <li>Community Support</li>
          </ul>
          <Button variant="outline" className="mt-auto border-gray-600 text-gray-200 hover:bg-gray-700/50 transition-all duration-300">Get Started</Button>
        </Card>
        {/* Pricing Card 2 (Featured) */}
        <Card className="p-10 rounded-xl border-2 border-blue-500 shadow-xl relative flex flex-col text-center scale-105 bg-gradient-to-br from-gray-800 to-blue-900/50 transition-all duration-500 hover:shadow-2xl hover:translate-y-[-4px] hover:scale-105">
          <div className="absolute top-0 right-0 -mt-3 mr-3 bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-xs font-semibold px-4 py-2 rounded-full shadow-lg">Most Popular</div>
          <h3 className="text-xl font-semibold text-white mb-3">Pro</h3>
          <p className="text-4xl font-bold text-white mb-6">$29<span className="text-base font-medium text-gray-400">/mo</span></p>
          <ul className="text-sm text-gray-300 space-y-3 mb-8 text-left list-disc list-inside">
            <li>Full Stats Access</li>
            <li>Advanced AI Queries</li>
            <li>Player Comparisons</li>
            <li>Trend Detection</li>
            <li>Priority Support</li>
          </ul>
          <Button className="mt-auto bg-gradient-to-r from-blue-500 to-cyan-500 text-white hover:from-blue-600 hover:to-cyan-600 shadow-lg hover:shadow-xl transition-all duration-300">Choose Pro</Button>
        </Card>
        {/* Pricing Card 3 */}
        <Card className="p-10 bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-600 shadow-lg transition-all duration-500 ease-in-out transform hover:shadow-xl hover:scale-105 hover:bg-gray-800 flex flex-col text-center">
          <h3 className="text-xl font-semibold text-white mb-3">Enterprise</h3>
          <p className="text-4xl font-bold text-white mb-6">Custom</p>
          <ul className="text-sm text-gray-300 space-y-3 mb-8 text-left list-disc list-inside">
            <li>API Access</li>
            <li>Custom Models</li>
            <li>Dedicated Support</li>
          </ul>
          <Button variant="outline" className="mt-auto hover:bg-gray-50 transition-colors duration-300">Contact Us</Button>
        </Card>
      </div>
    </section>
  );
} 
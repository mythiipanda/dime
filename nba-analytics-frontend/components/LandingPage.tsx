"use client";

import React from 'react';
import { LandingNavbar } from '@/components/landing/Navbar';
import { FeaturesSection } from '@/components/landing/FeaturesSection';
import { VisionSection } from '@/components/landing/VisionSection';
import { UseCasesSection } from '@/components/landing/UseCasesSection';
import { PricingSection } from '@/components/landing/PricingSection';
import { Footer } from '@/components/layout/Footer';
import { HeroSection } from '@/components/landing/HeroSection';

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen bg-[#000E0F] text-white overflow-x-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[40rem] left-1/4 -z-10 transform-gpu blur-3xl animate-[spin_80s_linear_infinite]" aria-hidden="true">
          <div className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-blue-900 to-indigo-800 opacity-10" 
              style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
        <div className="absolute top-[10%] right-[20%] -z-10 transform-gpu blur-3xl animate-[spin_60s_linear_infinite]" aria-hidden="true">
          <div className="aspect-[1155/678] w-[50rem] bg-gradient-to-r from-indigo-800 to-blue-900 opacity-10" 
              style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
        <div className="absolute bottom-[20%] left-[10%] -z-10 transform-gpu blur-3xl animate-[spin_70s_linear_infinite]" aria-hidden="true">
          <div className="aspect-[1155/678] w-[45rem] bg-gradient-to-tr from-blue-800 to-purple-900 opacity-10" 
              style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
        </div>
      </div>

      <LandingNavbar />

      <main className="flex-auto pt-20">
        <HeroSection />
        <FeaturesSection />
        <VisionSection />
        <UseCasesSection />
        <PricingSection />
      </main>
      {/* <p className='p-10 text-center'>Main Content Placeholder</p> */}

      <Footer />
    </div>
  );
}

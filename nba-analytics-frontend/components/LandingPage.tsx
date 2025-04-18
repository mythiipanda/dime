"use client";

import React from 'react';
import { LandingNavbar } from '@/components/landing/Navbar';
import { FeaturesSection } from '@/components/landing/FeaturesSection';
import { VisionSection } from '@/components/landing/VisionSection';
import { UseCasesSection } from '@/components/landing/UseCasesSection';
import { PricingSection } from '@/components/landing/PricingSection';
import { Footer } from '@/components/layout/Footer';

export default function LandingPage() {
  return (
    <div className="relative flex flex-col min-h-screen bg-gradient-to-br from-gray-950 via-blue-950 to-gray-900 text-white">
      <LandingNavbar />

      <main className="flex-auto">
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

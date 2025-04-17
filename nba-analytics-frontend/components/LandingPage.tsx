"use client";

import React from 'react';
import { LandingNavbar } from '@/components/landing/Navbar';
import { FeaturesSection } from '@/components/landing/FeaturesSection';
import { VisionSection } from '@/components/landing/VisionSection';
import { PricingSection } from '@/components/landing/PricingSection';
import { Footer } from '@/components/layout/Footer';

export default function LandingPage() {
  return (
    <div className="relative flex flex-col min-h-screen bg-white text-gray-900">
      <LandingNavbar />

      <main className="flex-auto">
        <FeaturesSection />
        <VisionSection />
        <PricingSection />
      </main>
      {/* <p className='p-10 text-center'>Main Content Placeholder</p> */}

      <Footer />
    </div>
  );
}

"use client";

import React from 'react';
import { LandingNavbar } from '@/components/landing/Navbar';
import { HeroSection } from '@/components/landing/HeroSection';
import { PerformanceInsightsSection } from '@/components/landing/PerformanceInsightsSection';
import { KeyFunctionalitiesSection } from '@/components/landing/KeyFunctionalitiesSection';
import { CollaborativeAiSection } from '@/components/landing/CollaborativeAiSection';
import { FinalCtaSection } from '@/components/landing/FinalCtaSection';
import { LandingFooter } from '@/components/landing/LandingFooter';

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen bg-gradient-to-br from-gray-950 via-black to-blue-950 text-gray-200 overflow-x-hidden">
      {/* Background decorative elements removed for a cleaner light mode start */}
      
      <LandingNavbar />

      <main className="flex-auto pt-16 md:pt-20">
        <HeroSection />
        <section id="features"><KeyFunctionalitiesSection /></section> 
        <section id="insights"><PerformanceInsightsSection /></section>
        <section id="ai-collaboration"><CollaborativeAiSection /></section>
        <FinalCtaSection />
      </main>

      <LandingFooter />
    </div>
  );
}

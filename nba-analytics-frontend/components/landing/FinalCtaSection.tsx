"use client";

import React from 'react';
import { WaitlistForm } from '@/components/landing/WaitlistForm';

export function FinalCtaSection() {
  return (
    <section id="waitlist-cta" className="py-16 md:py-24 bg-gray-900">
      <div className="container mx-auto max-w-3xl px-4 text-center">
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          Be the First to Experience Dime
        </h2>
        <p className="text-lg md:text-xl text-gray-300 mb-10 max-w-xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
          Join our waitlist to get early access, product updates, and help shape the future of AI in sports analytics.
        </p>
        <div className="flex justify-center animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
          <WaitlistForm />
        </div>
      </div>
    </section>
  );
} 
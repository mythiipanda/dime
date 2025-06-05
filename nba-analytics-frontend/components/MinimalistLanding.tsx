"use client";

import React from 'react';
import { WaitlistForm } from '@/components/landing/WaitlistForm';
import { Logo } from '@/components/layout/Logo';
import { TrendingUp, Target, Database } from 'lucide-react';

export function MinimalistLanding() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Minimal Navigation */}
      <nav className="container mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <Logo href="/" iconSize={6} textSize="lg" />
          <button className="text-sm border border-border rounded-lg px-4 py-2 hover:border-ring hover:bg-accent transition-all duration-200">
            Request Demo
          </button>
        </div>
      </nav>

      {/* Hero content - centered */}
      <div className="container mx-auto px-6 flex-1 flex items-center justify-center">
        <div className="text-center max-w-4xl mx-auto">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-medium tracking-tight mb-6 leading-tight">
            Meet Dime
            <span className="block text-primary font-medium">
              Your NBA Analytics Agent
            </span>
          </h1>
          
          <p className="text-muted-foreground text-lg md:text-xl mb-8 max-w-2xl mx-auto leading-relaxed">
            An autonomous agent that builds models, analyzes trades, and generates reports.
            Deploy it to handle the analytical work your team does manually.
          </p>
          
          <div className="flex justify-center mb-10">
            <WaitlistForm />
          </div>

          {/* Key capabilities in compact grid */}
          <div className="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto">
            <div className="flex flex-col items-center text-center p-4">
              <TrendingUp className="h-8 w-8 text-primary mb-3" />
              <span className="text-sm font-medium text-foreground">Predictive Models</span>
            </div>
            <div className="flex flex-col items-center text-center p-4">
              <Target className="h-8 w-8 text-primary mb-3" />
              <span className="text-sm font-medium text-foreground">Trade Analysis</span>
            </div>
            <div className="flex flex-col items-center text-center p-4">
              <Database className="h-8 w-8 text-primary mb-3" />
              <span className="text-sm font-medium text-foreground">Data Queries</span>
            </div>
          </div>
        </div>
      </div>

      {/* Compact Footer */}
      <footer className="border-t border-border bg-background text-muted-foreground py-4 mt-8">
        <div className="container mx-auto px-6 flex items-center justify-center">
          <div className="flex items-center">
            <Logo href="/" iconSize={4} hideText={true} className="mr-2" />
            <span className="text-xs text-muted-foreground">
              &copy; {new Date().getFullYear()} Dime. All rights reserved.
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
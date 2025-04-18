"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import React, { useState, useEffect } from 'react';

export function LandingNavbar() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  
  return (
    // Updated header styling based on Figma (Nodes 11:4206, 11:4223)
    <header className={`fixed top-4 left-4 right-4 z-50 px-3 py-1 transition-all duration-300 ease-in-out ${
      scrolled ? 'bg-background/80 backdrop-blur-md border border-border rounded-full shadow-lg' : 'bg-transparent'
    }`}>
      <div className="container mx-auto max-w-7xl px-3 h-10 flex items-center justify-between">
        {/* Logo - Based on Node 11:4208 */}
        <Link href="/" className="flex items-center gap-2 text-xl font-bold">
          {/* Replace with actual SVG/Component from Figma if available */}
          <div className="w-8 h-8 flex items-center justify-center bg-primary rounded-lg shadow">
             <span className='text-primary-foreground font-bold text-lg'>D</span> {/* Placeholder */} 
          </div>
           <span className="text-foreground font-bold">Dime</span> {/* Adjusted name */} 
        </Link>
        
        {/* Navigation Links - Simple text links */}
        <nav className="hidden md:flex items-center space-x-6">
          <a href="#features" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Features</a>
          <a href="#vision" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Vision</a>
          <a href="#pricing" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Pricing</a>
          {/* Add other links if needed */}
        </nav>
        
        {/* Auth Buttons */}
        <div className="flex items-center space-x-3">
          <SignedIn>
            <Link href="/dashboard">
              {/* Adjusted Button Style */}
              <Button size="sm">Dashboard</Button>
            </Link>
          </SignedIn>
          <SignedOut>
            {/* Adjusted Button Styles */}
             <SignInButton mode="modal">
               <Button variant="ghost" size="sm">Sign in</Button>
             </SignInButton>
             {/* Try Free uses same blue accent */}
             <SignInButton mode="modal">
              <Button size="sm">Try Free</Button>
             </SignInButton>
          </SignedOut>
        </div>
      </div>
    </header>
  );
}
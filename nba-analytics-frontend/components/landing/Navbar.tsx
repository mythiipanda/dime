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
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ease-in-out ${
      scrolled ? 'bg-[#000E0F]/80 backdrop-blur-md border-b border-white/10 shadow-lg' : 'bg-transparent border-b border-transparent'
    }`}>
      <div className="container mx-auto max-w-7xl px-4 h-16 flex items-center justify-between">
        {/* Logo - Based on Node 11:4208 */}
        <Link href="/" className="flex items-center gap-2 text-xl font-bold">
          {/* Replace with actual SVG/Component from Figma if available */}
          <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg shadow-md">
             <span className='text-black font-bold text-lg'>D</span> {/* Placeholder */} 
          </div>
           <span className="text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-300">Dime</span> {/* Adjusted name */} 
        </Link>
        
        {/* Navigation Links - Simple text links */}
        <nav className="hidden md:flex items-center space-x-6">
          <a href="#features" className="text-[#A7BEBE] hover:text-white text-sm font-medium transition-colors duration-200">Features</a>
          <a href="#vision" className="text-[#A7BEBE] hover:text-white text-sm font-medium transition-colors duration-200">Vision</a>
          <a href="#pricing" className="text-[#A7BEBE] hover:text-white text-sm font-medium transition-colors duration-200">Pricing</a>
          {/* Add other links if needed */}
        </nav>
        
        {/* Auth Buttons */}
        <div className="flex items-center space-x-3">
          <SignedIn>
            <Link href="/dashboard">
              {/* Adjusted Button Style */}
              <Button size="sm" className="bg-blue-500 text-white hover:bg-blue-600 font-semibold rounded-full px-5 py-1.5 shadow-md text-sm">
                Dashboard
              </Button>
            </Link>
          </SignedIn>
          <SignedOut>
            {/* Adjusted Button Styles */}
             <SignInButton mode="modal">
               <Button variant="ghost" size="sm" className="text-[#A7BEBE] hover:text-white hover:bg-white/5 rounded-full px-5 py-1.5 text-sm">
                 Sign in
               </Button>
             </SignInButton>
             {/* Try Free uses same blue accent */}
             <SignInButton mode="modal">
              <Button size="sm" className="bg-blue-500 text-white hover:bg-blue-600 font-semibold rounded-full px-5 py-1.5 shadow-md text-sm">
                 Try Free
               </Button>
             </SignInButton>
          </SignedOut>
        </div>
      </div>
    </header>
  );
}
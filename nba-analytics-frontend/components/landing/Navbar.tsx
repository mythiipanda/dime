"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import React, { useState, useEffect } from 'react';

export function LandingNavbar() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return (
    <header className={`fixed top-6 left-1/2 transform -translate-x-1/2 z-50 backdrop-blur-md bg-black/40 text-white rounded-2xl shadow-lg transition-all duration-300 ease-in-out ${scrolled ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4 pointer-events-none'}`}>
      <div className="mx-auto px-6 py-3 flex items-center justify-between space-x-6">
        <Link href="/" className="text-xl font-bold mr-4">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">Dime</span>
        </Link>
        <div className="hidden md:flex items-center space-x-6">
          <a href="#features" className="text-white/90 hover:text-white transition-colors duration-200 text-sm font-medium">Features</a>
          <a href="#vision" className="text-white/90 hover:text-white transition-colors duration-200 text-sm font-medium">Vision</a>
          <a href="#pricing" className="text-white/90 hover:text-white transition-colors duration-200 text-sm font-medium">Pricing</a>
        </div>
        <div className="flex space-x-4">
          <SignedIn>
            <Link href="/dashboard"><Button variant="outline" className="border-white/50 bg-transparent text-white/90 hover:bg-white/20 hover:border-white hover:text-white transition-all duration-200 px-3 py-1 text-sm h-8">Dashboard</Button></Link>
          </SignedIn>
          <SignedOut>
            {/* Redirects are likely handled globally or via Clerk provider config */}
            <SignInButton mode="modal">
              <Button variant="outline" className="border-white/50 text-white/90 hover:bg-white/20 hover:border-white hover:text-white transition-all duration-200 px-3 py-1 text-sm h-8">Sign in</Button>
            </SignInButton>
          </SignedOut>
          <SignedOut>
            <SignInButton mode="modal">
              <Button className="bg-gradient-to-r from-blue-500 to-cyan-500 text-white hover:from-blue-600 hover:to-cyan-600 transition-colors duration-200 shadow-sm hover:shadow-md px-3 py-1 text-sm h-8">Try Free</Button>
            </SignInButton>
          </SignedOut>
        </div>
      </div>
    </header>
  );
}
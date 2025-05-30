"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import React, { useState, useEffect } from 'react';
import { Logo } from '@/components/layout/Logo';
import { Sheet, SheetContent, SheetTrigger, SheetClose } from "@/components/ui/sheet";
import { MenuIcon, Sparkles } from "lucide-react";

export function LandingNavbar() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20); 
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  
  const navLinkClasses = "text-sm font-medium transition-colors duration-200 text-gray-400 hover:text-white px-1 lg:px-1.5 xl:px-2";
  const mobileNavLinkClasses = "text-lg font-medium text-gray-200 hover:text-white py-1.5 text-center";

  return (
    <header className={`fixed top-3 left-1/2 transform -translate-x-1/2 w-[calc(100%-2rem)] sm:w-[calc(100%-2.5rem)] max-w-5xl xl:max-w-6xl z-50 px-3 sm:px-4 py-1.5 sm:py-2 transition-all duration-300 ease-in-out ${ 
      scrolled 
        ? 'bg-black/70 backdrop-blur-xl border border-white/15 rounded-full shadow-2xl shadow-blue-500/25'
        : 'bg-transparent border-transparent rounded-full'
    }`}>
      <div className="container mx-auto max-w-7xl px-1 sm:px-2 h-10 flex items-center justify-between">
        <Logo href="/" iconSize={5} textSize="lg" />
      
        <nav className="hidden md:flex items-center space-x-2 lg:space-x-3 xl:space-x-4">
          <Link href="#features" className={navLinkClasses}>Features</Link>
          <Link href="#insights" className={navLinkClasses}>How it Works</Link> 
          <Link href="#ai-collaboration" className={navLinkClasses}>AI Agent</Link>
        </nav>
      
        <div className="hidden md:flex items-center space-x-2">
          <SignedOut>
             <SignInButton mode="modal">
               <Button variant="ghost" size="sm" className="text-sm font-medium text-gray-300 hover:text-white hover:bg-white/10 rounded-md px-3">Sign In</Button>
             </SignInButton>
          </SignedOut>
          <SignedIn>
            <UserButton afterSignOutUrl="/" />
            <Link href="/overview">
              <Button size="sm" className="bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-semibold shadow-md hover:shadow-lg hover:shadow-cyan-500/30 transition-all duration-300 rounded-md px-4">Dashboard</Button>
            </Link>
          </SignedIn>
        </div>

        <div className="md:hidden flex items-center">
          <SignedIn>
            <UserButton afterSignOutUrl="/" />
            <div className="w-2"></div>
          </SignedIn>
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="text-gray-300 hover:text-white hover:bg-white/10 rounded-md">
                <MenuIcon className="h-5 w-5" />
                <span className="sr-only">Open menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[280px] sm:w-[300px] p-5 bg-gray-950/95 backdrop-blur-xl border-l border-white/20 text-gray-200 flex flex-col">
              <div className="mb-6 text-center">
                <Logo href="/" iconSize={6} textSize="xl" />
              </div>
              <nav className="flex flex-col space-y-3 mb-auto">
                <SheetClose asChild><Link href="#features" className={mobileNavLinkClasses}>Features</Link></SheetClose>
                <SheetClose asChild><Link href="#insights" className={mobileNavLinkClasses}>How it Works</Link></SheetClose>
                <SheetClose asChild><Link href="#ai-collaboration" className={mobileNavLinkClasses}>AI Agent</Link></SheetClose>
              </nav>
              <div className="mt-auto space-y-3 pt-4 border-t border-white/10">
                <SignedOut>
                  <SheetClose asChild>
                    <SignInButton mode="modal">
                      <Button variant="outline" className="w-full text-gray-200 border-white/30 hover:bg-white/20">Sign In</Button>
                    </SignInButton>
                  </SheetClose>
                </SignedOut>
                <SignedIn>
                  <SheetClose asChild>
                    <Link href="/overview" className="w-full">
                      <Button className="w-full bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-semibold">Dashboard</Button>
                    </Link>
                  </SheetClose>
                </SignedIn>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}

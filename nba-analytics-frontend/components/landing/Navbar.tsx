"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs"; // Added UserButton
import React, { useState, useEffect } from 'react';
import { Logo } from '@/components/layout/Logo'; // Import Logo
import { Sheet, SheetContent, SheetTrigger, SheetClose } from "@/components/ui/sheet"; // Added Sheet components
import { MenuIcon } from "lucide-react"; // Added MenuIcon

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
      <div className="container mx-auto max-w-7xl px-3 h-12 flex items-center justify-between">
        <Logo href="/" iconSize={6} textSize="xl" />
      
        {/* Desktop Navigation Links */}
        <nav className="hidden md:flex items-center space-x-6">
          <Link href="#features" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Features</Link>
          <Link href="/browse" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Browse</Link>
          <Link href="/learn" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Learn</Link>
          <Link href="#pricing" className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors duration-200">Pricing</Link>
        </nav>
      
        {/* Desktop Auth and CTA Buttons */}
        <div className="hidden md:flex items-center space-x-3">
          <SignedIn>
            <UserButton afterSignOutUrl="/" />
            <Link href="/dashboard">
              <Button size="sm">Dashboard</Button>
            </Link>
          </SignedIn>
          <SignedOut>
             <SignInButton mode="modal">
               <Button variant="ghost" size="sm">Sign In</Button>
             </SignInButton>
             {/* <Button variant="outline" size="sm">Download</Button> // Aura doesn't explicitly list Download here, can be added back if needed */}
             <SignInButton mode="modal">
              <Button size="sm">Get Started</Button> {/* Changed "Try Free" to "Get Started" */}
             </SignInButton>
          </SignedOut>
        </div>

        {/* Mobile Menu Trigger */}
        <div className="md:hidden">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon">
                <MenuIcon className="h-6 w-6" />
                <span className="sr-only">Open menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[300px] sm:w-[400px] p-6">
              <div className="flex flex-col h-full">
                <div className="mb-8">
                  <Logo href="/" iconSize={6} textSize="xl" />
                </div>
                <nav className="flex flex-col space-y-5 text-lg mb-auto">
                  <SheetClose asChild>
                    <Link href="#features" className="text-muted-foreground hover:text-foreground font-medium">Features</Link>
                  </SheetClose>
                  <SheetClose asChild>
                    <Link href="/browse" className="text-muted-foreground hover:text-foreground font-medium">Browse</Link>
                  </SheetClose>
                  <SheetClose asChild>
                    <Link href="/learn" className="text-muted-foreground hover:text-foreground font-medium">Learn</Link>
                  </SheetClose>
                  <SheetClose asChild>
                    <Link href="#pricing" className="text-muted-foreground hover:text-foreground font-medium">Pricing</Link>
                  </SheetClose>
                </nav>
                <div className="mt-auto space-y-3">
                  <SignedOut>
                    <SheetClose asChild>
                      <SignInButton mode="modal">
                        <Button variant="outline" className="w-full">Sign In</Button>
                      </SignInButton>
                    </SheetClose>
                    <SheetClose asChild>
                      <SignInButton mode="modal">
                        <Button className="w-full">Get Started</Button>
                      </SignInButton>
                    </SheetClose>
                    {/* <SheetClose asChild>
                      <Button variant="secondary" className="w-full">Download</Button>
                    </SheetClose> */}
                  </SignedOut>
                  <SignedIn>
                    <SheetClose asChild>
                      <Link href="/dashboard" className="w-full">
                        <Button className="w-full">Dashboard</Button>
                      </Link>
                    </SheetClose>
                     <div className="pt-2"> <UserButton afterSignOutUrl="/" /> </div>
                  </SignedIn>
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
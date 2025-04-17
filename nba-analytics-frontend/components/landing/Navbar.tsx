"use client";

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";

export function LandingNavbar() {
  return (
    <header className="fixed top-0 w-full z-50 bg-white/95 backdrop-blur-md border-b border-gray-100 transition-all duration-300">
      <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-2xl font-bold">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Dime</span>
        </Link>
        <div className="hidden md:flex items-center space-x-8">
          <a href="#features" className="text-gray-600 hover:text-blue-600 transition-colors duration-200 font-medium">Features</a>
          <a href="#vision" className="text-gray-600 hover:text-blue-600 transition-colors duration-200 font-medium">Vision</a>
          <a href="#pricing" className="text-gray-600 hover:text-blue-600 transition-colors duration-200 font-medium">Pricing</a>
        </div>
        <div className="flex space-x-4">
          <SignedIn>
            <Link href="/dashboard"><Button variant="outline" className="border-gray-300 text-gray-700 hover:bg-blue-50 hover:border-blue-500 hover:text-blue-600 transition-all duration-200">Dashboard</Button></Link>
          </SignedIn>
          <SignedOut>
            {/* Redirects are likely handled globally or via Clerk provider config */}
            <SignInButton mode="modal">
              <Button variant="outline" className="border-gray-300 text-gray-700 hover:bg-blue-50 hover:border-blue-500 hover:text-blue-600 transition-all duration-200">Sign in</Button>
            </SignInButton>
          </SignedOut>
          <SignedOut>
            <SignInButton mode="modal">
              <Button className="bg-blue-600 text-white hover:bg-blue-700 transition-colors duration-200 shadow-sm hover:shadow-md">Try Free</Button>
            </SignInButton>
          </SignedOut>
        </div>
      </div>
    </header>
  );
} 
import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { CircleDot } from 'lucide-react';
import { cn } from '@/lib/utils'; // Import cn

interface NavbarProps {
  transparent?: boolean;
}

export function Navbar({ transparent = false }: NavbarProps) {
  return (
    <nav className={cn(
      `w-full ${transparent ? 'absolute top-0 z-50 bg-transparent py-6' : 'bg-background/80 backdrop-blur-md py-6'}`,
      "animate-in fade-in-0 slide-in-from-top-4 duration-500" // Navbar entrance
    )}>
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        <div className="flex items-center gap-3 animate-in fade-in-0 slide-in-from-left-3 duration-500 delay-100">
          <div className="rounded-lg bg-primary p-2 transition-transform hover:scale-110">
            <CircleDot className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-2xl font-bold">Dime</span>
        </div>
        
        <div className="hidden md:flex items-center space-x-6 animate-in fade-in-0 duration-500 delay-200">
          <Link href="/features" className="text-base font-medium text-gray-200 hover:text-white transition-all hover:scale-105 duration-200">
            Features
          </Link>
          <Link href="/pricing" className="text-base font-medium text-gray-200 hover:text-white transition-all hover:scale-105 duration-200">
            Pricing
          </Link>
          <Link href="/about" className="text-base font-medium text-gray-200 hover:text-white transition-all hover:scale-105 duration-200">
            About
          </Link>
        </div>
        
        <div className="hidden md:flex items-center space-x-4 animate-in fade-in-0 slide-in-from-right-3 duration-500 delay-300">
          <Link href="/dashboard">
            <Button variant="outline" className="px-4 py-2 border-white/20 hover:bg-white/10 text-white">
              Sign In
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button className="bg-white hover:bg-gray-100 text-black font-medium px-4 py-2">
              Try Demo
            </Button>
          </Link>
        </div>
      </div>
    </nav>
  );
}

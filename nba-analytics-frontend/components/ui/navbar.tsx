import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { CircleDot } from 'lucide-react';

interface NavbarProps {
  transparent?: boolean;
}

export function Navbar({ transparent = false }: NavbarProps) {
  return (
    <nav className={`w-full ${transparent ? 'absolute top-0 z-50 bg-transparent py-6' : 'bg-background/80 backdrop-blur-md py-6'}`}>
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary p-2">
            <CircleDot className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-2xl font-bold">Dime</span>
        </div>
        
        <div className="hidden md:flex items-center space-x-6">
          <Link href="/features" className="text-base font-medium text-gray-200 hover:text-white transition-colors">
            Features
          </Link>
          <Link href="/pricing" className="text-base font-medium text-gray-200 hover:text-white transition-colors">
            Pricing
          </Link>
          <Link href="/about" className="text-base font-medium text-gray-200 hover:text-white transition-colors">
            About
          </Link>
        </div>
        
        <div className="hidden md:flex items-center space-x-4">
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

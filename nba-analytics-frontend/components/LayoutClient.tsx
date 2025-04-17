"use client";
import React from 'react';
import { usePathname } from 'next/navigation';
import { SidebarNav } from '@/components/layout/SidebarNav';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Menu, Settings, CircleDot } from 'lucide-react';
import { ModeToggle } from '@/components/mode-toggle';
import LandingPage from '@/components/LandingPage';
import { SignedIn, SignedOut, UserButton, SignInButton } from "@clerk/nextjs";

interface LayoutClientProps {
  children: React.ReactNode;
}

export default function LayoutClient({ children }: LayoutClientProps) {
  const pathname = usePathname();
  const isLanding = pathname === '/';
  if (isLanding) {
    return <LandingPage />;
  }

  return (
    <div className="relative flex min-h-screen">
      {!isLanding && (
        <aside className="fixed hidden h-screen w-72 border-r bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 px-6 py-8 lg:block">
          <div className="flex h-full flex-col justify-between">
            <div className="space-y-6">
              {/* Logo */}
              <div className="flex items-center gap-2 px-2">
                <div className="rounded-lg bg-primary p-2">
                  <CircleDot className="h-6 w-6 text-primary-foreground" />
                </div>
                <div className="flex flex-col">
                  <span className="text-xl font-semibold tracking-tight">Dime</span>
                  <span className="text-sm font-regular text-muted-foreground">NBA Analytics</span>
                </div>
              </div>
              {/* Navigation */}
              <SidebarNav />
            </div>
            {/* User Profile */}
            <div className="space-y-4">
              <SignedIn>
                <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3">
                  <UserButton afterSignOutUrl="/" />
                  {/* Add settings/profile link if needed later */}
                  <ModeToggle />
                </div>
              </SignedIn>
              <SignedOut>
                <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3">
                  <SignInButton mode="modal">
                    <Button variant="outline" className="w-full">Sign In</Button>
                  </SignInButton>
                  <ModeToggle />
                </div>
              </SignedOut>
            </div>
          </div>
        </aside>
      )}
      {!isLanding && (
        <header className="fixed top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 lg:hidden px-6">
          <div className="flex h-16 items-center gap-4 px-4">
            <Button variant="ghost" size="icon" className="hover:bg-accent">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle menu</span>
            </Button>
            <div className="flex items-center gap-2">
              <div className="rounded-lg bg-primary p-1">
                <CircleDot className="h-5 w-5 text-primary-foreground" />
              </div>
              <div className="flex flex-col">
                <span className="text-xl font-semibold tracking-tight">Dime</span>
                <span className="text-sm font-regular text-muted-foreground">NBA Analytics</span>
              </div>
            </div>
            <div className="ml-auto flex items-center space-x-2">
              <SignedOut>
                <SignInButton mode="modal">
                  <Button variant="ghost" size="sm">Sign In</Button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
              <ModeToggle />
            </div>
          </div>
        </header>
      )}
      <main className={isLanding ? 'flex-auto' : 'flex-1 overflow-y-auto lg:pl-72'}>
        <div className={isLanding ? 'w-full' : 'max-w-7xl mx-auto min-h-screen px-6 py-8 lg:px-8 lg:py-12'}>
          {children}
        </div>
      </main>
    </div>
  );
}

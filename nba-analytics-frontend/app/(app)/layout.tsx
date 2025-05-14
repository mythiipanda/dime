"use client"; // Needed for Sheet, UserButton, etc.
import React, { useState } from 'react';
import { SidebarNav } from '@/components/layout/SidebarNav';
import { Button } from '@/components/ui/button';
import { Menu, PanelLeftClose, PanelRightOpen, Users } from 'lucide-react';
import { ModeToggle } from '@/components/mode-toggle';
import { SignedIn, SignedOut, UserButton, SignInButton, RedirectToSignIn, useUser } from "@clerk/nextjs";
import { Logo } from '@/components/layout/Logo'; // Adjusted path
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";

import { cn } from "@/lib/utils"; // Import cn for conditional classes

// Define props for the layout
interface AppLayoutProps {
  children: React.ReactNode;
}

// This component now serves as the layout for the (app) group
export default function AppLayout({ children }: AppLayoutProps) {
  const [isCollapsed, setIsCollapsed] = useState(true); // Default to collapsed
  const toggleSidebar = () => setIsCollapsed(!isCollapsed);
  // Get user data
  const { user, isSignedIn } = useUser();

  return (
    <div className={cn("relative flex min-h-screen")}>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "fixed hidden top-0 left-0 bottom-0 border-r transition-all duration-300 ease-in-out lg:flex flex-col justify-between overflow-y-auto",
          "bg-muted dark:bg-gray-950/70 dark:backdrop-blur-md border-border dark:border-white/10", // Use bg-muted for light, dark overrides
          isCollapsed ? "w-20 px-2 py-4" : "w-60 px-4 py-6"
        )}
      >
        <div className={cn("space-y-6", isCollapsed && "flex flex-col items-center")}>
          <Logo
            className={cn(isCollapsed ? "px-0" : "px-2")}
            iconSize={isCollapsed ? 6 : 6}
            textSize={isCollapsed ? undefined : "xl"}
            hideText={isCollapsed}
          />
          <SidebarNav isCollapsed={isCollapsed} />
        </div>

        {/* Bottom Section: User Profile & Collapse Toggle - Simplified */}
        <div className={cn("mt-auto space-y-3 border-t border-border pt-3", isCollapsed ? "px-0" : "px-0")}> {/* Added border-t, adjusted padding */}
          {/* Signed Out State */}
          <SignedOut>
            <div className={cn("flex", isCollapsed ? "justify-center" : "px-2")}>
              <SignInButton mode="modal">
                <Button
                  variant="outline" // Consistent variant
                  size={isCollapsed ? "icon" : "sm"}
                  className={cn(!isCollapsed && "w-full")}
                  title="Sign In"
                >
                  {isCollapsed ? <Users className="h-5 w-5" /> : "Sign In"}
                </Button>
              </SignInButton>
            </div>
          </SignedOut>
          {/* Signed In State */}
          <SignedIn>
            <div className={cn(
              "flex items-center",
              isCollapsed ? "flex-col gap-3 justify-center" : "gap-2 px-2 justify-between" // Adjusted for better spacing
            )}>
              <UserButton afterSignOutUrl="/" />
              {!isCollapsed && isSignedIn && user && (
                <span className="text-sm font-medium truncate flex-1 text-center"> {/* Centered name when expanded */}
                  {user.fullName || `${user.firstName || ''} ${user.lastName || ''}`.trim() || user.username || "User"}
                </span>
              )}
              <ModeToggle />
            </div>
          </SignedIn>

          {/* Collapse Toggle Button */}
          <div className={cn(isCollapsed ? "flex justify-center" : "px-2")}>
            <Button
                onClick={toggleSidebar}
                variant="ghost"
                size="icon"
                className={cn("w-full flex justify-center text-muted-foreground hover:text-foreground", isCollapsed ? "h-9" : "h-9")} // Standardized height
                title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              >
                {isCollapsed ? <PanelRightOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
                <span className="sr-only">{isCollapsed ? "Expand" : "Collapse"}</span>
              </Button>
          </div>
        </div>
      </aside>

      {/* Mobile Header */}
      <header className={cn(
        "fixed top-0 z-30 w-full border-b lg:hidden px-4 sm:px-6",
        "bg-muted dark:bg-gray-950/70 dark:backdrop-blur-md border-border dark:border-white/10" // Light/Dark styles inside cn
      )}>
        <div className="flex h-16 items-center gap-4">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="hover:bg-accent">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-6">
               {/* Add VisuallyHidden Title if needed again for Sheet
               <VisuallyHidden><DialogTitle>Navigation Menu</DialogTitle></VisuallyHidden>
               */}
              <Logo className="mb-6 px-2" iconSize={6} textSize="xl" />
              <SidebarNav isCollapsed={false} />
            </SheetContent>
          </Sheet>
          <div className="flex-1 flex justify-center">
             <Logo iconSize={5} textSize="lg" />
          </div>
          <div className="flex items-center space-x-2">
            <SignedOut>
              <SignInButton mode="modal">
                <Button variant="ghost" size="sm">Sign In</Button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <ModeToggle />
              <UserButton afterSignOutUrl="/" />
            </SignedIn>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main
        className={cn(
          'flex-1 overflow-y-auto transition-all duration-300 ease-in-out',
          'pt-16 lg:pt-0',
          isCollapsed ? "lg:pl-20" : "lg:pl-60"
        )}
      >
        <div className={cn(
          'max-w-full mx-auto px-4 sm:px-6 py-8 lg:px-8 lg:py-12 flex-1 flex flex-col', // max-w-full to allow content to use gradient
          'animate-in fade-in-0 slide-in-from-bottom-4 duration-500'
        )}>
          <SignedIn>
            {children}
          </SignedIn>
          <SignedOut>
            {/* Redirect if not signed in */}
            <RedirectToSignIn />
          </SignedOut>

        </div>
      </main>
    </div>
  );
}
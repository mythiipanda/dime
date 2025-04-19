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
  const [isCollapsed, setIsCollapsed] = useState(false); // State for collapse
  const toggleSidebar = () => setIsCollapsed(!isCollapsed);
  // Get user data
  const { user, isSignedIn } = useUser(); 

  return (
    <div className={cn("relative flex min-h-screen")}>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "fixed hidden h-screen border-r bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 transition-all duration-300 ease-in-out lg:flex flex-col justify-between",
          // Use w-60 for expanded, w-20 for collapsed. Adjust padding.
          isCollapsed ? "w-20 px-2 py-4" : "w-60 px-4 py-6" 
        )}
      >
        <div className={cn("space-y-6", isCollapsed && "flex flex-col items-center")}>
          <Logo
            // Keep logo padding consistent or adjust as needed
            className={cn(isCollapsed ? "px-0" : "px-2")} 
            iconSize={isCollapsed ? 6 : 6}
            // Pass undefined when collapsed to let Logo handle hiding text
            textSize={isCollapsed ? undefined : "xl"} 
            hideText={isCollapsed} // Explicitly tell Logo to hide text
          />
          <SidebarNav isCollapsed={isCollapsed} />
        </div>

        {/* Bottom Section: User Profile & Collapse Toggle */}
        <div className={cn("mt-auto space-y-2")}>
          {/* Signed Out State */}
          <SignedOut>
            <div className={cn("flex items-center rounded-lg border bg-card", isCollapsed ? "justify-center p-2" : "gap-2 px-3 py-2")}>
              <SignInButton mode="modal">
                <Button 
                  variant={isCollapsed ? "ghost" : "outline"} 
                  size={isCollapsed ? "icon" : "default"} 
                  className={cn(!isCollapsed && "w-full")}
                >
                  {isCollapsed ? <Users className="h-5 w-5" /> : "Sign In"}
                </Button>
              </SignInButton>
            </div>
          </SignedOut>
          {/* Signed In State */}
          <SignedIn>
            <div className={cn(
              "flex items-center rounded-lg border bg-card", 
              // Keep vertical layout for collapsed state
              isCollapsed ? "flex-col gap-2 p-2" : "gap-2 px-3 py-2" 
            )}>
              {/* Expanded view: Button, Name, Toggle */}
              {!isCollapsed && (
                <>
                  <UserButton afterSignOutUrl="/" />
                  {/* Display username/name if available */}
                  {isSignedIn && user && (
                    <span className="text-sm font-medium truncate ml-1">
                      {/* Prioritize fullName, then combine first/last, then fallback */}
                      {user.fullName || `${user.firstName || ''} ${user.lastName || ''}`.trim() || user.username || "User"}
                    </span>
                  )}
                  <div className={cn("flex items-center ml-auto gap-1")}>
                    <ModeToggle />
                  </div>
                </>
              )}
              {/* Collapsed view: Button, Toggle */}
              {isCollapsed && (
                <>
                  <UserButton afterSignOutUrl="/" />
                  <ModeToggle />
                </>
              )}
            </div>
          </SignedIn>
          
          {/* Collapse Toggle Button - Moved inside footer */}
          <Button 
              onClick={toggleSidebar}
              variant="ghost" 
              size="icon" 
              className={cn("w-full flex justify-center text-muted-foreground hover:text-foreground", isCollapsed ? "h-8" : "h-8")}
              title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            >
              {isCollapsed ? <PanelRightOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
              <span className="sr-only">{isCollapsed ? "Expand" : "Collapse"}</span>
            </Button>
        </div>
      </aside>

      {/* Mobile Header - Reverted to previous known good state, potentially needs Sheet fixes if used*/}
      <header className="fixed top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 lg:hidden px-4 sm:px-6">
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
      {/* Ensure children are always rendered, protected by Clerk components */}
      <main
        className={cn(
          'flex-1 overflow-y-auto transition-all duration-300 ease-in-out',
          'pt-16 lg:pt-0', // Keep top padding for mobile header
          isCollapsed ? "lg:pl-20" : "lg:pl-60" // Adjust left padding based on collapse state
        )}
      >
        <div className='max-w-7xl mx-auto min-h-screen px-4 sm:px-6 py-8 lg:px-8 lg:py-12'>
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
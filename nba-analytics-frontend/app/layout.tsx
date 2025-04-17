import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { ThemeProvider } from "@/components/theme-provider";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Menu, Settings, CircleDot } from "lucide-react";
import { ModeToggle } from "@/components/mode-toggle";
import "./globals.css";
import { cn } from '@/lib/utils'

export const metadata: Metadata = {
  title: {
    default: "Dime - NBA Analytics Hub",
    template: "%s | Dime"
  },
  description: "Advanced NBA analytics and insights powered by AI. Get real-time stats, player analysis, and game predictions.",
  keywords: ["NBA", "basketball", "analytics", "statistics", "AI", "sports data", "player analysis"],
  authors: [{ name: "Dime Analytics" }],
  openGraph: {
    title: "Dime - NBA Analytics Hub",
    description: "Advanced NBA analytics and insights powered by AI",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Dime - NBA Analytics Hub",
    description: "Advanced NBA analytics and insights powered by AI",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head />
      <body className={cn('min-h-screen bg-background font-sans antialiased', GeistSans.className)}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <div className="relative flex min-h-screen">
            {/* Desktop Sidebar */}
            <aside className="fixed hidden h-screen w-64 border-r bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 px-4 py-6 lg:block">
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
                  <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3">
                    <Avatar>
                      <AvatarImage src="/avatar.png" alt="User" />
                      <AvatarFallback>U</AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <p className="text-sm font-regular leading-none">John Doe</p>
                      <p className="text-sm font-regular text-muted-foreground mt-1">Pro Plan</p>
                    </div>
                    <Button variant="ghost" size="icon" className="hover:bg-accent">
                      <Settings className="h-4 w-4" />
                      <span className="sr-only">Settings</span>
                    </Button>
                    <ModeToggle />
                  </div>
                </div>
              </div>
            </aside>

            {/* Mobile Header */}
            <header className="fixed top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75 lg:hidden">
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
              </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto lg:pl-64">
              <div className="container min-h-screen px-4 py-6 lg:px-8 lg:py-8">
                {children}
              </div>
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}

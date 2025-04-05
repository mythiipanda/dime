import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { HomeIcon, LineChartIcon, Package2Icon, PackageIcon, UsersIcon, BotIcon, SettingsIcon } from "lucide-react";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NBA Analytics Platform", // Updated title
  description: "AI-Powered NBA Data Analysis", // Updated description
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Ensure no whitespace between html and body tags
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
          {/* Sidebar */}
          <div className="hidden border-r bg-muted/40 md:block">
            <div className="flex h-full max-h-screen flex-col gap-2">
              <div className="flex h-14 items-center border-b px-4 lg:h-[60px] lg:px-6">
                <a href="/" className="flex items-center gap-2 font-semibold">
                  <Package2Icon className="h-6 w-6" /> {/* Replace with NBA logo/icon */}
                  <span className="">NBA Analytics</span>
                </a>
              </div>
              <div className="flex-1">
                <ScrollArea className="h-full py-4"> {/* Added padding */}
                  <nav className="grid items-start px-2 text-sm font-medium lg:px-4">
                    {/* TODO: Use Next.js Link component and manage active state */}
                    <a
                      href="/" // Link to dashboard page
                      className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary"
                      // Add logic for active state: e.g., bg-muted text-primary
                    >
                      <BotIcon className="h-4 w-4" />
                      Agent Dashboard
                    </a>
                    <a
                      href="/players" // Link to players page
                      className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary"
                    >
                      <UsersIcon className="h-4 w-4" />
                      Players
                    </a>
                    <a
                      href="/teams" // Link to teams page
                      className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary"
                    >
                      <PackageIcon className="h-4 w-4" /> {/* Replace icon */}
                      Teams
                    </a>
                    <a
                      href="/games" // Link to games page
                      className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary"
                    >
                       <PackageIcon className="h-4 w-4" /> {/* Replace icon */}
                      Games
                    </a>
                     <a
                      href="/shot-charts" // Link to shot charts page
                      className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary"
                    >
                      <LineChartIcon className="h-4 w-4" />
                      Shot Charts
                    </a>
                  </nav>
                </ScrollArea>
              </div>
               {/* Optional: Footer section in sidebar */}
               <div className="mt-auto border-t p-4">
                 <Button size="sm" variant="ghost" className="w-full justify-start">
                   <SettingsIcon className="mr-2 h-4 w-4" />
                   Settings
                 </Button>
               </div>
            </div>
          </div>
          {/* Main Content Area Wrapper (Child pages will go here) */}
          <div className="flex flex-col max-h-screen"> {/* Ensure main area doesn't overflow screen */}
             {/* Header */}
            <header className="flex h-14 items-center gap-4 border-b bg-background px-4 lg:h-[60px] lg:px-6 sticky top-0 z-10">
              <div className="w-full flex-1">
                {/* Header content can be dynamic based on page or stay static */}
                 <h1 className="font-semibold text-lg">NBA Agent Interface</h1>
              </div>
              <Avatar className="h-8 w-8">
                <AvatarImage src="/placeholder-user.jpg" alt="User" />
                <AvatarFallback>U</AvatarFallback>
              </Avatar>
            </header>
            {/* Page Content Rendered Here */}
            {children} {/* This renders the page content */}
          </div>
        </div>
      </body>
    </html>
  );
}

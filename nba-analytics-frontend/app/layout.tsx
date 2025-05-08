import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { ThemeProvider } from "@/components/theme-provider";
import { ClerkProvider } from '@clerk/nextjs';
// import { Footer } from "@/components/layout/Footer"; // Footer will be moved to specific pages
import "./globals.css";
import { cn } from '@/lib/utils';

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

export default function RootLayout({ children, }: { children: React.ReactNode; }) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        {/* <head /> - Removed empty head tag */}
        <body className={cn('min-h-screen bg-background font-sans antialiased', GeistSans.className)}>
          <ThemeProvider
            attribute="class"
            defaultTheme="dark"
            enableSystem
            disableTransitionOnChange
          >
            <div className="flex flex-col min-h-screen"> {/* Footer stickiness container */}
              <main className="flex-grow">{children}</main>
              {/* Footer removed from root - applied per-page or in specific layouts */}
            </div>
          </ThemeProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}

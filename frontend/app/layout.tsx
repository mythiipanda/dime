import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dime NBA Analyst",
  description: "Analyst chat plus datasets for the 2025-26 NBA season.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="antialiased">{children}</body>
    </html>
  );
}

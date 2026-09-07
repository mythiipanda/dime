import type { Metadata } from "next";
import { Inter, Inter_Tight } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-body" });
const tight = Inter_Tight({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "Dime NBA Analyst",
  description: "Analyst chat plus datasets for the 2025-26 NBA season.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${tight.variable}`}>{children}</body>
    </html>
  );
}

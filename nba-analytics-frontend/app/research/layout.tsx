import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Research | NBA Analytics",
  description: "Advanced NBA research tools and analytics insights",
};

export default function ResearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
} 
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "NBA Analytics Dashboard - Your central hub for basketball insights",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
} 
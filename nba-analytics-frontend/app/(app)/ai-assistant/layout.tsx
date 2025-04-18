import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dime Assistant | NBA Analytics",
  description: "Your AI-powered NBA research companion. Ask questions about players, teams, and games to get instant insights.",
};

export default function AIAssistantLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
} 
"use client"; // Mark as a Client Component

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  BotIcon,
  UsersIcon,
  BarChart2Icon,
  TrophyIcon,
  CalendarIcon,
  HomeIcon,
  ActivityIcon,
  LineChartIcon,
  BookOpenIcon,
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

interface SidebarNavProps {
  isCollapsed: boolean;
}

const navSections: NavSection[] = [
  {
    title: "Overview",
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: HomeIcon },
      { href: '/ai-assistant', label: 'AI Assistant', icon: BotIcon },
      { href: '/research', label: 'Research', icon: BookOpenIcon },
    ]
  },
  {
    title: "Analysis",
    items: [
      { href: '/players', label: 'Players', icon: UsersIcon },
      { href: '/teams', label: 'Teams', icon: TrophyIcon },
      { href: '/games', label: 'Games', icon: CalendarIcon },
      { href: '/statistics', label: 'Statistics', icon: BarChart2Icon },
    ]
  },
  {
    title: "Tools",
    items: [
      { href: '/shot-charts', label: 'Shot Charts', icon: LineChartIcon },
      { href: '/chat', label: 'Chat', icon: ActivityIcon },
    ]
  }
];

export function SidebarNav({ isCollapsed }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <TooltipProvider delayDuration={0}>
      <nav className={cn("space-y-6", isCollapsed && "space-y-2")}>
        {navSections.map((section) => (
          <div key={section.title} className="space-y-1">
            {!isCollapsed && (
              <h4 className="px-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                {section.title}
              </h4>
            )}
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Tooltip key={item.href} disableHoverableContent={!isCollapsed}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        "group flex items-center gap-3 rounded-md text-sm font-medium transition-colors duration-150 ease-in-out", // Changed to rounded-md, adjusted transition
                        isCollapsed ? "justify-center p-2 h-9 w-9" : "px-3 py-2", // Adjusted padding for expanded
                        isActive
                          ? "text-primary bg-primary/10 border-l-4 border-primary" // Active: left border, subtle bg, primary text
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground", // Inactive: hover to accent
                        isCollapsed && isActive && "border-l-0 border-t-4 border-primary rounded-b-md rounded-t-none" // Collapsed active: top border
                      )}
                    >
                      <Icon className={cn("h-5 w-5", isActive ? "text-primary" : "group-hover:text-accent-foreground")} /> {/* Icon color change on active/hover */}
                      <span className={cn("whitespace-nowrap", isCollapsed && "sr-only", isActive ? "font-semibold" : "font-medium")}> {/* Bolder text for active */}
                        {item.label}
                      </span>
                    </Link>
                  </TooltipTrigger>
                  {isCollapsed && (
                    <TooltipContent side="right" className="flex items-center gap-4">
                      {item.label}
                    </TooltipContent>
                  )}
                </Tooltip>
              );
            })}
          </div>
        ))}
      </nav>
    </TooltipProvider>
  );
}
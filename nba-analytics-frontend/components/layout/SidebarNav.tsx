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
                        "flex items-center gap-3 rounded-lg text-sm font-regular transition-all hover:bg-accent hover:text-foreground",
                        isCollapsed ? "justify-center p-2 h-9 w-9" : "px-4 py-2",
                        isActive
                          ? "bg-accent text-accent-foreground hover:text-accent-foreground"
                          : "text-muted-foreground hover:bg-muted"
                      )}
                    >
                      <Icon className={cn("h-5 w-5", isCollapsed && "mx-auto")} />
                      <span className={cn("whitespace-nowrap", isCollapsed && "sr-only")}>
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
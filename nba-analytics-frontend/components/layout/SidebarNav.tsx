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

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavSection {
  title: string;
  items: NavItem[];
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

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="space-y-6">
      {navSections.map((section) => (
        <div key={section.title} className="space-y-3">
          <h4 className="px-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground"> {/* Size 4: text-sm font-semibold */}
            {section.title}
          </h4>
          <div className="space-y-1">
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-4 py-2 text-sm font-regular transition-all hover:bg-accent hover:text-accent-foreground",
                    {
                      "bg-accent text-accent-foreground": isActive,
                      "text-muted-foreground": !isActive,
                    }
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
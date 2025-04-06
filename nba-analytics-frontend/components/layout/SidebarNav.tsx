"use client"; // Mark as a Client Component

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import clsx from 'clsx';
import {
  BotIcon,
  UsersIcon,
  PackageIcon, // Using PackageIcon as placeholder for Teams/Games for now
  LineChartIcon,
} from 'lucide-react';

// Define navigation items
const navItems = [
  { href: '/', label: 'Agent Dashboard', icon: BotIcon },
  { href: '/players', label: 'Players', icon: UsersIcon },
  { href: '/teams', label: 'Teams', icon: PackageIcon }, // Placeholder icon
  { href: '/games', label: 'Games', icon: PackageIcon }, // Placeholder icon
  { href: '/shot-charts', label: 'Shot Charts', icon: LineChartIcon },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="grid items-start px-2 text-sm font-medium lg:px-4">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = pathname === item.href;
        // Basic active check: exact match for now.
        // Could be enhanced later e.g., pathname.startsWith(item.href) for nested routes if needed.

        return (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              "flex items-center gap-3 rounded-lg px-3 py-2 transition-all hover:text-primary",
              {
                "bg-muted text-primary": isActive,
                "text-muted-foreground": !isActive,
              }
            )}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
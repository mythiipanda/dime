import { CircleDot } from 'lucide-react';
import Link from 'next/link';

interface LogoProps {
  className?: string;
  iconSize?: number;
  textSize?: 'sm' | 'md' | 'lg' | 'xl';
  hideText?: boolean;
  href?: string; // Add href prop
}

export function Logo({ className, iconSize = 6, textSize = 'xl', hideText = false, href = "/dashboard" }: LogoProps) { // Add href to props and default
  const iconClass = `h-${iconSize} w-${iconSize}`;
  const titleSizeClass = `text-${textSize}`;
  const subtitleSizeClass = textSize === 'xl' ? 'text-sm' : 'text-xs'; // Adjust subtitle size based on title

  return (
    <Link href={href} className={`flex items-center gap-2 ${className}`}>
      <div className="rounded-lg bg-primary p-2">
        <CircleDot className={`${iconClass} text-primary-foreground`} />
      </div>
      {!hideText && (
        <div className="flex flex-col">
          <span className={`${titleSizeClass} font-semibold tracking-tight`}>Dime</span>
          <span className={`${subtitleSizeClass} font-regular text-muted-foreground`}>NBA Analytics</span>
        </div>
      )}
    </Link>
  );
} 
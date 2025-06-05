import { CircleDot } from 'lucide-react';
import Link from 'next/link';

interface LogoProps {
  className?: string;
  iconSize?: number;
  textSize?: 'sm' | 'md' | 'lg' | 'xl';
  hideText?: boolean;
  href?: string;
}

export function Logo({ className, iconSize = 6, textSize = 'xl', hideText = false, href = "/" }: LogoProps) {
  const iconClass = `h-${iconSize} w-${iconSize}`;
  const titleSizeClass = `text-${textSize}`;

  return (
    <Link href={href} className={`flex items-center gap-3 group ${className}`}>
      <div className="rounded-lg bg-white p-2 group-hover:bg-gray-100 transition-colors duration-200">
        <CircleDot className={`${iconClass} text-black`} />
      </div>
      {!hideText && (
        <span className={`${titleSizeClass} font-medium tracking-tight text-white group-hover:text-gray-300 transition-colors duration-200`}>
          Dime
        </span>
      )}
    </Link>
  );
}
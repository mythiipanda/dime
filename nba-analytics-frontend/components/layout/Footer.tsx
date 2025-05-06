import Link from 'next/link';
import { Logo } from '@/components/layout/Logo'; // Import Logo
import { TwitterIcon, YoutubeIcon, LinkedinIcon } from 'lucide-react'; // Import social icons

export function Footer() {
  return (
    <footer className="py-8 border-t border-border bg-background text-muted-foreground mt-20">
      <div className="container mx-auto max-w-7xl px-4 flex flex-col md:flex-row items-center justify-between gap-6 md:gap-0">
        <div className="flex items-center"> {/* Removed mb-4 md:mb-0 for better centering with more items */}
          <Logo href="/" iconSize={5} hideText={true} className="mr-3" />
          <span className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} Dime. All rights reserved.
          </span>
        </div>
        <div className="flex items-center space-x-6">
          <Link href="/terms" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Terms
          </Link>
          <Link href="/privacy" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Privacy
          </Link>
          <Link href="/contact" className="text-xs text-muted-foreground hover:text-foreground transition-colors"> {/* Changed href to /contact */}
            Contact
          </Link>
          <div className="flex items-center space-x-4">
            <Link href="https://x.com" target="_blank" rel="noopener noreferrer" aria-label="X (formerly Twitter)" className="text-muted-foreground hover:text-foreground transition-colors">
              <TwitterIcon className="h-5 w-5" />
            </Link>
            <Link href="https://youtube.com" target="_blank" rel="noopener noreferrer" aria-label="YouTube" className="text-muted-foreground hover:text-foreground transition-colors">
              <YoutubeIcon className="h-5 w-5" />
            </Link>
            <Link href="https://linkedin.com" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn" className="text-muted-foreground hover:text-foreground transition-colors">
              <LinkedinIcon className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
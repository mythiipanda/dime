import Link from 'next/link';

export function Footer() {
  return (
    <footer className="py-8 border-t border-border bg-background text-muted-foreground mt-20">
      <div className="container mx-auto max-w-7xl px-4 flex flex-col md:flex-row items-center justify-between">
        <div className="flex items-center mb-4 md:mb-0">
          <div className="w-7 h-7 flex items-center justify-center bg-primary rounded-md shadow-sm mr-2">
            <span className='text-primary-foreground font-bold text-base'>D</span>
          </div>
          <span className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} Dime. All rights reserved.
          </span>
        </div>
        <div className="flex space-x-6">
          <Link href="/terms" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Terms
          </Link>
          <Link href="/privacy" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Privacy
          </Link>
          <Link href="#" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Contact
          </Link>
        </div>
      </div>
    </footer>
  );
}
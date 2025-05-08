import Link from 'next/link';
import { Logo } from '@/components/layout/Logo'; // Assuming you have a Logo component
import { Twitter, Youtube, Linkedin } from 'lucide-react'; // Adjusted social icons

export function LandingFooter() {
  const currentYear = new Date().getFullYear();

  const footerLinkClasses = "text-sm text-gray-400 hover:text-white transition-colors duration-200";
  const socialLinkClasses = "text-gray-400 hover:text-white transition-colors duration-200";

  return (
    <footer className="bg-gray-950 border-t border-white/10">
      <div className="container mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-3">
            <Logo href="/" iconSize={6} />
            <p className="text-sm text-gray-400">
              &copy; {currentYear} Dime. All rights reserved.
            </p>
          </div>
          
          <div className="flex items-center gap-x-5 sm:gap-x-6">
            <Link href="/terms" className={footerLinkClasses}>Terms</Link>
            <Link href="/privacy" className={footerLinkClasses}>Privacy</Link>
            <Link href="/contact" className={footerLinkClasses}>Contact</Link>
            <div className="flex space-x-4">
              <Link href="https://twitter.com/DimeAnalytics" target="_blank" rel="noopener noreferrer" className={socialLinkClasses}><span className="sr-only">Twitter</span><Twitter className="h-5 w-5" /></Link>
              <Link href="https://youtube.com/DimeAnalytics" target="_blank" rel="noopener noreferrer" className={socialLinkClasses}><span className="sr-only">YouTube</span><Youtube className="h-5 w-5" /></Link>
              <Link href="https://linkedin.com/company/DimeAnalytics" target="_blank" rel="noopener noreferrer" className={socialLinkClasses}><span className="sr-only">LinkedIn</span><Linkedin className="h-5 w-5" /></Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
} 
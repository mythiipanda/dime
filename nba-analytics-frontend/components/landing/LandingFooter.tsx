import Link from 'next/link';
import { Logo } from '@/components/layout/Logo'; // Assuming you have a Logo component
import { Github, Twitter, Linkedin } from 'lucide-react'; // Example social icons

export function LandingFooter() {
  const currentYear = new Date().getFullYear();

  const footerLinkClasses = "text-sm text-gray-500 hover:text-primary transition-colors duration-200";
  const socialLinkClasses = "text-gray-400 hover:text-primary transition-colors duration-200";

  return (
    <footer className="bg-gray-50 border-t border-gray-200">
      <div className="container mx-auto max-w-7xl px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 gap-8 mb-8">
          {/* Logo and Branding */}
          <div className="md:col-span-1 lg:col-span-2 space-y-4">
            <Logo href="/" iconSize={8} />
            <p className="text-sm text-gray-500 max-w-xs">
              Dime: Your AI Agent for Unparalleled NBA Intelligence.
            </p>
          </div>

          {/* Product Links */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Product</h3>
            <ul className="mt-4 space-y-3">
              <li><Link href="#features" className={footerLinkClasses}>Features</Link></li>
              <li><Link href="#pricing" className={footerLinkClasses}>Pricing</Link></li>
              <li><Link href="/dashboard" className={footerLinkClasses}>Dashboard</Link></li>
              {/* Add more product-related links if necessary */}
            </ul>
          </div>

          {/* Company Links */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Company</h3>
            <ul className="mt-4 space-y-3">
              <li><Link href="/about" className={footerLinkClasses}>About Us</Link></li>
              <li><Link href="/blog" className={footerLinkClasses}>Blog</Link></li> 
              <li><Link href="/contact" className={footerLinkClasses}>Contact</Link></li>
            </ul>
          </div>

          {/* Legal Links */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase">Legal</h3>
            <ul className="mt-4 space-y-3">
              <li><Link href="/privacy" className={footerLinkClasses}>Privacy Policy</Link></li>
              <li><Link href="/terms" className={footerLinkClasses}>Terms of Service</Link></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-200 pt-8 flex flex-col sm:flex-row justify-between items-center">
          <p className="text-sm text-gray-500">
            &copy; {currentYear} Dime Analytics. All rights reserved.
          </p>
          <div className="flex space-x-5 mt-4 sm:mt-0">
            <Link href="#" className={socialLinkClasses}><span className="sr-only">Twitter</span><Twitter className="h-5 w-5" /></Link>
            <Link href="#" className={socialLinkClasses}><span className="sr-only">GitHub</span><Github className="h-5 w-5" /></Link>
            <Link href="#" className={socialLinkClasses}><span className="sr-only">LinkedIn</span><Linkedin className="h-5 w-5" /></Link>
          </div>
        </div>
      </div>
    </footer>
  );
} 
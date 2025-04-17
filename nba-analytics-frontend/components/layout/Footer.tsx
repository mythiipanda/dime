import Link from 'next/link';

export function Footer() {
  return (
    <footer className="bg-white py-12 border-t border-gray-100">
      <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between">
        <div className="flex items-center">
          <span className="text-blue-600 font-bold mr-2">Dime</span>
          <span className="text-sm text-gray-600">
            {new Date().getFullYear()} All rights reserved.
          </span>
        </div>
        <div className="flex space-x-6 mt-4 md:mt-0">
          {/* Add actual links if needed */}
          <Link href="/terms" className="text-sm text-gray-600 hover:text-blue-600">
            Terms of Service
          </Link>
          <Link href="/privacy" className="text-sm text-gray-600 hover:text-blue-600">
            Privacy Policy
          </Link>
          <Link href="#" className="text-sm text-gray-600 hover:text-blue-600">
            Contact Us
          </Link>
        </div>
      </div>
    </footer>
  );
}
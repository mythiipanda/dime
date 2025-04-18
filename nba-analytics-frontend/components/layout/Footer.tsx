import Link from 'next/link';

export function Footer() {
  return (
    <footer className="bg-gray-900 py-6 border-t border-gray-800">
      <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between">
        <div className="flex items-center">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400 font-bold mr-2 text-sm">Dime</span>
          <span className="text-xs text-gray-400">
            {new Date().getFullYear()} All rights reserved.
          </span>
        </div>
        <div className="flex space-x-4 mt-3 md:mt-0">
          {/* Add actual links if needed */}
          <Link href="/terms" className="text-xs text-gray-400 hover:text-blue-400">
            Terms
          </Link>
          <Link href="/privacy" className="text-xs text-gray-400 hover:text-blue-400">
            Privacy
          </Link>
          <Link href="#" className="text-xs text-gray-400 hover:text-blue-400">
            Contact
          </Link>
        </div>
      </div>
    </footer>
  );
}
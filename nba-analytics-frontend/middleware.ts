import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';

const isProtectedRoute = createRouteMatcher([
  '/dashboard(.*)',
]);

export default clerkMiddleware(); // Let Clerk handle protection based on config

export const config = {
  // Protect all routes including api/trpc routes
  // Please edit this to allow other routes to be public as needed.
  // See https://clerk.com/docs/references/nextjs/clerk-middleware for more information about configuring your Middleware
  matcher: [
    '/((?!.+\.[\w]+$|_next).*)', // Match all routes except static files and _next
    '/',                        // Match the root route
    '/(api|trpc)(.*)'           // Match API routes
  ],
  publicRoutes: ['/', '/sign-in', '/sign-up'], // Explicitly mark landing and auth pages as public
};

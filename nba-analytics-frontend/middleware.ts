import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';

// This is the default export, Clerk handles protection automatically
// based on the publicRoutes config below.
export default clerkMiddleware();

export const config = {
  matcher: [
    '/((?!.+\.[\w]+$|_next).*)', // Match all routes except static files and _next
    '/',                        // Match the root route
    '/(api|trpc)(.*)'           // Match API routes
  ],
  // Routes that are publicly accessible. All other routes will be protected by default.
  // Ensure that new app routes like /overview, /player-intel are NOT listed here.
  publicRoutes: [
    '/',
    '/sign-in',
    '/sign-up',
    '/features', // Assuming this is a public landing page section
    '/pricing',  // Assuming this is a public landing page section
    '/about',    // Assuming this is a public landing page section
    '/api/waitlist' // Public API endpoint
  ],
};

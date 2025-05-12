import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Add rewrites for local development proxy to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*', // Matches any request starting with /api/
        // Proxy to local backend running on port 8000, preserving the /api part of the path
        destination: 'http://localhost:8000/api/:path*',
      },
    ]
  },
};

export default nextConfig;

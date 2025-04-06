import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Add rewrites for local development proxy to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // Proxy to local backend running on port 8000
        destination: 'http://localhost:8000/:path*',
      },
    ]
  },
};

export default nextConfig;

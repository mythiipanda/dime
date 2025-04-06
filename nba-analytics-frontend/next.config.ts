import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export', // Enable static export
  // Required for static export, especially for environments like GitHub Pages
  images: {
    unoptimized: true,
  },
};

export default nextConfig;

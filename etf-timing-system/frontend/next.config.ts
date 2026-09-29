import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // `next dev` still talks to the separately started local FastAPI process.
  // Vercel Services owns this route in production before it reaches Next.js.
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return [];
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8000/api/v1/:path*',
      },
    ];
  },
};

export default nextConfig;

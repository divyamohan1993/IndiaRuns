/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The /sandbox API route shells out to the real rank.py; keep it server-side.
  experimental: {
    // allow reading repo-root files (rank.py, data sample) from the API route
  },
};

export default nextConfig;

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone server output → small Cloud Run container (node server.js).
  output: "standalone",
};

export default nextConfig;

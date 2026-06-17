/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone server output → small Cloud Run container (node server.js).
  output: "standalone",
  // Same-origin proxy for local/Cloud Shell dev: the browser hits /beacon/* on this origin
  // and Next forwards to the backend server-side — avoids CORS and Cloud Shell's auth-walled
  // cross-port Web Preview. Target overridable via BEACON_API_URL (default localhost:8000).
  // In production we set NEXT_PUBLIC_API_URL at build time and the client calls the backend
  // directly (public Cloud Run URLs, no preview gateway), so this proxy isn't used there.
  async rewrites() {
    const target = (process.env.BEACON_API_URL || "http://localhost:8000").replace(/\/$/, "");
    return [{ source: "/beacon/:path*", destination: `${target}/:path*` }];
  },
};

export default nextConfig;
